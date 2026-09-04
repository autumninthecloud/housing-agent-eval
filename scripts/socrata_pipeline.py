"""
socrata_pipeline.py

Shared, dependency-free helpers for pulling a Socrata (NYC Open Data) dataset,
upserting it into a canonical "current" CSV, writing an immutable dated history
snapshot, and contributing a per-dataset entry to the weekly manifest.

Design reference: CLAUDE.md, "Phase 2 design (locked, pre-implementation)".

Key properties implemented here:
- No third-party dependencies (urllib + csv only).
- Per-dataset failure isolation: if a pull fails, this dataset's canonical
  file and history snapshot are left completely untouched, and the caller
  gets back a manifest entry with status "failed" instead of raising past
  this module (see run_dataset_refresh's docstring for the exact contract).
- Upsert semantics: canonical file has exactly one row per entity ID; a
  fresh pull overwrites existing IDs and adds new ones. This assumes the API
  is itself the source of truth for "latest state" of a given ID (true for
  both HPD violations and 311 requests, which expose mutable status fields).
"""

from __future__ import annotations

import csv
import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Callable, Optional


SOCRATA_BASE_URL = "https://data.cityofnewyork.us/resource"
# Large filtered queries on the 311 dataset (28M+ rows) measured 267-350s for
# a single page regardless of $limit or $order — the WHERE filter itself is
# the fixed cost, not pagination. 600s gives real headroom above that.
REQUEST_TIMEOUT_SECONDS = 600
PAGE_SIZE = 5000  # SODA API page size per request; safely under typical caps


@dataclass
class DatasetConfig:
    """Everything needed to pull, upsert, and snapshot one Socrata dataset.

    Attributes:
        name: short key used in file names and manifest keys, e.g. "hpd" or "311".
        dataset_id: the Socrata 4x4 dataset ID, e.g. "wvxf-dwi5".
        id_field: the column name that uniquely identifies a row (used as the
            upsert key). Must be a field actually returned by `columns`.
        date_field: the column used for the rolling-window filter, e.g.
            "novissueddate" or "created_date". Must be a Socrata datetime-typed
            field for the $where clause below to work.
        columns: ordered list of column names to request from the API and to
            write to the canonical/history CSVs. This is the trimmed schema
            from CLAUDE.md, not the full source schema.
        extra_where: an additional SoQL boolean expression ANDed onto the date
            filter, e.g. "agency = 'HPD'" for the 311 dataset. Pass None if no
            extra filter is needed.
        window_days: size of the rolling window in days. Defaults to 365 per
            the locked Phase 2 design (trailing 12 months).
        canonical_path: where the upserted "current" CSV lives.
        history_dir: directory where dated history snapshots are written.
        page_size: SODA API $limit per request. Defaults to the module-level
            PAGE_SIZE (0 means "use the default"). Large tables where the
            $where filter itself is the dominant cost (see split_query)
            should override this upward, since a bigger page amortizes that
            fixed per-query cost over more rows rather than paying it once
            per 5,000-row page.
        split_query: if True, run_dataset_refresh fetches this dataset with
            two separate queries instead of one full-window re-fetch:
            (1) rows new since the last successful run, and (2) rows within
            the window that are still open (closed_date_field IS NULL) and
            so might have had a status change. See CLAUDE.md's Phase 2
            design ("311 pull strategy") for why this exists — a full
            365-day re-fetch of the 311 dataset costs ~3 hours/week at this
            table's real-world size, which the two-query split cuts to
            ~10-15 minutes. Requires closed_date_field to be set.
        closed_date_field: column name holding the closed-date/timestamp,
            used only when split_query is True to find still-open rows via
            "{closed_date_field} IS NULL". Must be in columns.
    """

    name: str
    dataset_id: str
    id_field: str
    date_field: str
    columns: list[str]
    extra_where: Optional[str] = None
    window_days: int = 365
    canonical_path: str = ""
    history_dir: str = ""
    page_size: int = 0
    split_query: bool = False
    closed_date_field: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.canonical_path:
            self.canonical_path = f"data/live/{self.name}_current.csv"
        if not self.history_dir:
            self.history_dir = "data/live/history"
        if self.id_field not in self.columns:
            raise ValueError(
                f"id_field {self.id_field!r} must be included in columns for "
                f"dataset {self.name!r}, so it's present in every fetched row."
            )
        if not self.page_size:
            self.page_size = PAGE_SIZE
        if self.split_query and not self.closed_date_field:
            raise ValueError(
                f"split_query=True for dataset {self.name!r} requires "
                f"closed_date_field to be set."
            )
        if self.closed_date_field and self.closed_date_field not in self.columns:
            raise ValueError(
                f"closed_date_field {self.closed_date_field!r} must be "
                f"included in columns for dataset {self.name!r}."
            )


class DatasetRefreshError(Exception):
    """Raised internally when a pull fails. Always caught within
    run_dataset_refresh — callers should never see this; they get a
    manifest entry with status 'failed' instead. Kept as a real exception
    (not silently swallowed deeper in the call stack) so the specific
    failure point is easy to find in tests or interactive debugging.
    """


def _build_soql_where(config: DatasetConfig, since: date) -> str:
    """Builds the $where clause: date-window filter, optionally ANDed with
    an extra filter (e.g. 311's agency = 'HPD'). Used both for the
    single-query (full-window) path and, with `since` set to the last
    successful run's date instead of the window start, as the "new rows"
    half of a split-query dataset's fetch."""
    since_str = since.strftime("%Y-%m-%dT00:00:00")
    clause = f"{config.date_field} >= '{since_str}'"
    if config.extra_where:
        clause = f"({clause}) AND ({config.extra_where})"
    return clause


def _build_still_open_where(config: DatasetConfig, window_since: date) -> str:
    """Builds the $where clause for the "still open, needs a status
    re-check" half of a split-query dataset: rows created within the
    rolling window that haven't closed yet. Deliberately does NOT use
    :updated_at — tested against the live 311 dataset and rejected, since
    it reflects bulk reindex events rather than genuine per-row edits (see
    CLAUDE.md's Phase 2 design for the numbers)."""
    since_str = window_since.strftime("%Y-%m-%dT00:00:00")
    clause = f"({config.date_field} >= '{since_str}') AND ({config.closed_date_field} IS NULL)"
    if config.extra_where:
        clause = f"({clause}) AND ({config.extra_where})"
    return clause


def _fetch_page(
    config: DatasetConfig, where_clause: str, offset: int, app_token: str
) -> list[dict[str, Any]]:
    """Fetches a single page of rows from the SODA API. Raises
    DatasetRefreshError on any HTTP or JSON-decoding failure — callers should
    not need to inspect urllib exceptions directly."""
    params = {
        "$select": ",".join(config.columns),
        "$where": where_clause,
        "$limit": str(config.page_size),
        "$offset": str(offset),
        "$order": config.id_field,
    }
    url = f"{SOCRATA_BASE_URL}/{config.dataset_id}.json?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"X-App-Token": app_token})

    try:
        with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        raise DatasetRefreshError(
            f"HTTP {exc.code} from Socrata for dataset {config.name!r} "
            f"(offset={offset}): {exc.reason}"
        ) from exc
    except urllib.error.URLError as exc:
        raise DatasetRefreshError(
            f"Network error reaching Socrata for dataset {config.name!r} "
            f"(offset={offset}): {exc.reason}"
        ) from exc
    except (socket.timeout, TimeoutError) as exc:
        # urlopen only wraps OSErrors raised while sending the request into
        # URLError; a timeout while reading the response (h.getresponse())
        # propagates unwrapped, so it needs its own handler here to honor
        # run_dataset_refresh's "never raises past this module" contract.
        raise DatasetRefreshError(
            f"Timed out reaching Socrata for dataset {config.name!r} "
            f"(offset={offset}) after {REQUEST_TIMEOUT_SECONDS}s"
        ) from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise DatasetRefreshError(
            f"Could not decode JSON from Socrata for dataset {config.name!r} "
            f"(offset={offset}): {exc}"
        ) from exc


def fetch_all_rows(
    config: DatasetConfig, where_clause: str, app_token: str
) -> list[dict[str, Any]]:
    """Fetches every row matching where_clause, paging through the SODA API
    until a short page signals the end. Raises DatasetRefreshError if any
    page fails — this is intentional: a partial fetch must not be treated as
    a complete one, since that would corrupt the upsert (see module
    docstring on per-dataset atomicity).

    Takes the where_clause pre-built rather than building it internally, so
    callers (run_dataset_refresh) can pass either the single full-window
    clause or, for a split-query dataset, either half of the two-query
    fetch — see _build_soql_where and _build_still_open_where."""
    all_rows: list[dict[str, Any]] = []
    offset = 0

    while True:
        page = _fetch_page(config, where_clause, offset, app_token)
        all_rows.extend(page)
        if len(page) < config.page_size:
            break
        offset += config.page_size

    return all_rows


def _read_canonical_csv(path: str, columns: list[str]) -> dict[str, dict[str, Any]]:
    """Reads the existing canonical CSV into a dict keyed by row ID (the
    caller passes columns[0] equivalent via config.id_field at call sites).
    Returns an empty dict if the file doesn't exist yet (first-ever run)."""
    if not os.path.exists(path):
        return {}

    rows_by_id: dict[str, dict[str, Any]] = {}
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows_by_id[row[columns[0]]] = row
    return rows_by_id


def _write_csv(path: str, columns: list[str], rows: list[dict[str, Any]]) -> None:
    """Writes rows to a CSV, creating parent directories as needed. Writes
    to a temp file and renames into place, so a crash mid-write can never
    leave a half-written canonical file on disk — this is the concrete
    mechanism behind CLAUDE.md's 'no partial writes' guarantee."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in columns})
    os.replace(tmp_path, path)


def upsert_rows(
    config: DatasetConfig, fetched_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    """Merges freshly-fetched rows into the existing canonical file's rows.

    Returns (new_rows, updated_rows, total_count_after_upsert):
        new_rows: rows whose ID was not previously in the canonical file.
        updated_rows: rows whose ID existed before and whose content changed.
            Rows that were re-fetched but are byte-for-byte identical to what
            was already on disk are NOT included here — the manifest should
            reflect real change, not just "the API returned this ID again".
        total_count_after_upsert: row count of the canonical file post-merge.

    Does not write anything to disk — see write_canonical_and_snapshot for
    that. Kept separate so the upsert logic is independently testable.
    """
    existing = _read_canonical_csv(config.canonical_path, config.columns)

    new_rows: list[dict[str, Any]] = []
    updated_rows: list[dict[str, Any]] = []

    for row in fetched_rows:
        row_id = str(row[config.id_field])
        normalized_row = {col: ("" if row.get(col) is None else str(row.get(col))) for col in config.columns}

        if row_id not in existing:
            new_rows.append(normalized_row)
            existing[row_id] = normalized_row
        elif existing[row_id] != normalized_row:
            updated_rows.append(normalized_row)
            existing[row_id] = normalized_row
        # else: unchanged, no action — not counted as new or updated

    return new_rows, updated_rows, len(existing)


def write_canonical_and_snapshot(
    config: DatasetConfig, merged_rows_by_id: dict[str, dict[str, Any]], run_date: date
) -> None:
    """Writes the upserted canonical file and a dated, immutable history
    snapshot. Both writes go through the same atomic temp-file-then-rename
    path as _write_csv. History snapshots are never overwritten if a file
    for this run_date already exists (defends against accidentally
    re-running the same day and silently mutating a 'frozen' snapshot)."""
    all_rows = list(merged_rows_by_id.values())
    _write_csv(config.canonical_path, config.columns, all_rows)

    history_path = os.path.join(config.history_dir, f"{config.name}_{run_date.isoformat()}.csv")
    if os.path.exists(history_path):
        raise DatasetRefreshError(
            f"History snapshot {history_path} already exists — refusing to "
            f"overwrite an immutable snapshot. If this run genuinely needs "
            f"to re-run today, delete the existing snapshot manually first."
        )
    _write_csv(history_path, config.columns, all_rows)


def run_dataset_refresh(
    config: DatasetConfig, app_token: str, run_date: Optional[date] = None
) -> dict[str, Any]:
    """Runs the full refresh for one dataset: fetch, upsert, write canonical
    + history snapshot, and return this dataset's manifest entry.

    Contract: this function NEVER raises. Any failure (network, HTTP, decode,
    or the immutable-snapshot guard in write_canonical_and_snapshot) is
    caught here and converted into a manifest entry with status "failed" and
    an error message — this is what makes per-dataset failure isolation work
    at the call-site level (see run_all_datasets below), matching the
    per-dataset failure model in CLAUDE.md.

    On success, returns a manifest entry matching the schema in CLAUDE.md's
    "Handoff to the insight agent" section: status, new_count, updated_count,
    total_current, new_violations/new_rows, updated_violations/updated_rows.
    Uses the generic keys "new_rows"/"updated_rows" here; callers building
    the final manifest.json can rename per dataset if they want the
    dataset-specific key names shown in CLAUDE.md (e.g. new_violations).
    """
    if run_date is None:
        run_date = date.today()
    window_since = run_date - timedelta(days=config.window_days)

    try:
        if config.split_query:
            # Two smaller queries instead of one full-window re-fetch — see
            # DatasetConfig.split_query and CLAUDE.md's Phase 2 design for
            # why (a full 365-day re-fetch of the 311 dataset costs ~3
            # hours/week at its real-world row count).
            last_run_str = _last_history_snapshot_date(config)
            new_since = (
                datetime.strptime(last_run_str, "%Y-%m-%d").date()
                if last_run_str
                else window_since
            )
            new_rows_where = _build_soql_where(config, new_since)
            still_open_where = _build_still_open_where(config, window_since)

            fetched_rows = fetch_all_rows(config, new_rows_where, app_token)
            fetched_rows += fetch_all_rows(config, still_open_where, app_token)
        else:
            where_clause = _build_soql_where(config, window_since)
            fetched_rows = fetch_all_rows(config, where_clause, app_token)

        new_rows, updated_rows, _ = upsert_rows(config, fetched_rows)

        # Re-read to get the full merged set for writing (upsert_rows already
        # did the merge in-memory via `existing`, but recomputes cleanly here
        # for clarity and to avoid passing large mutable state back and forth).
        existing = _read_canonical_csv(config.canonical_path, config.columns)
        for row in fetched_rows:
            row_id = str(row[config.id_field])
            existing[row_id] = {col: ("" if row.get(col) is None else str(row.get(col))) for col in config.columns}

        write_canonical_and_snapshot(config, existing, run_date)

        return {
            "status": "success",
            "new_count": len(new_rows),
            "updated_count": len(updated_rows),
            "total_current": len(existing),
            "new_rows": new_rows,
            "updated_rows": updated_rows,
        }

    except DatasetRefreshError as exc:
        return {
            "status": "failed",
            "error": str(exc),
            "last_successful_run": _last_history_snapshot_date(config),
        }


def _last_history_snapshot_date(config: DatasetConfig) -> Optional[str]:
    """Looks at the history directory to report the most recent successful
    run's date, for the manifest's last_successful_run field on failure."""
    if not os.path.isdir(config.history_dir):
        return None
    prefix = f"{config.name}_"
    dates = []
    for filename in os.listdir(config.history_dir):
        if filename.startswith(prefix) and filename.endswith(".csv"):
            date_part = filename[len(prefix):-len(".csv")]
            try:
                dates.append(datetime.strptime(date_part, "%Y-%m-%d").date())
            except ValueError:
                continue
    return max(dates).isoformat() if dates else None


def run_all_datasets(
    configs: list[DatasetConfig], app_token: str, run_date: Optional[date] = None
) -> dict[str, Any]:
    """Runs run_dataset_refresh for every config independently — one
    dataset's failure has no effect on another's execution, per the locked
    per-dataset failure model. Returns the full manifest dict, ready to be
    written to weekly_manifest.json as-is (with config.name as each dataset's
    key, matching CLAUDE.md's manifest schema)."""
    if run_date is None:
        run_date = date.today()

    manifest: dict[str, Any] = {
        "run_date": run_date.isoformat(),
        "datasets": {},
    }

    for config in configs:
        manifest["datasets"][config.name] = run_dataset_refresh(config, app_token, run_date)

    return manifest


def write_manifest(manifest: dict[str, Any], path: str = "data/live/weekly_manifest.json") -> None:
    """Writes the manifest to disk, atomically (temp file + rename), so a
    crash mid-write never leaves a half-written manifest for the insight
    agent to trip over."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    os.replace(tmp_path, path)


def get_app_token() -> str:
    """Reads the Socrata app token from the environment. Raises a clear
    error immediately if it's missing, rather than letting every dataset
    fail individually with a less obvious auth error."""
    token = os.environ.get("NYC_OPEN_DATA_APP_TOKEN")
    if not token:
        raise RuntimeError(
            "NYC_OPEN_DATA_APP_TOKEN is not set. In GitHub Actions this "
            "should come from a repository secret; locally, export it in "
            "your shell before running this script."
        )
    return token
