"""
socrata_pipeline.py

Shared, dependency-free helpers for pulling a Socrata (NYC Open Data) dataset,
upserting it into a canonical "current" CSV, and contributing a per-dataset
entry to the weekly manifest.

Design reference: CLAUDE.md, "Phase 2 design (locked, pre-implementation)".

Key properties implemented here:
- No third-party dependencies (urllib + csv only).
- Per-dataset failure isolation: if a pull fails, this dataset's canonical
  file is left completely untouched, and the caller gets back a manifest
  entry with status "failed" instead of raising past this module (see
  run_dataset_refresh's docstring for the exact contract).
- Upsert semantics: canonical file has exactly one row per entity ID; a
  fresh pull overwrites existing IDs and adds new ones. This assumes the API
  is itself the source of truth for "latest state" of a given ID (true for
  both HPD violations and 311 requests, which expose mutable status fields).
- No dated history snapshots: canonical CSVs + weekly_manifest.json are
  committed to the repo each run and are the only durable state. A
  split-query dataset's "last successful run" cutoff is read back from the
  previously-committed manifest (see _last_successful_run_for), not from
  local files — this is what makes it work correctly on an ephemeral CI
  runner, which gets a fresh checkout with no local run history at all.
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
            write to the canonical CSV. This is the trimmed schema from
            CLAUDE.md, not the full source schema.
        extra_where: an additional SoQL boolean expression ANDed onto the date
            filter, e.g. "agency = 'HPD'" for the 311 dataset. Pass None if no
            extra filter is needed.
        window_days: size of the rolling window in days. Defaults to 365 per
            the locked Phase 2 design (trailing 12 months).
        canonical_path: where the upserted "current" CSV lives. This and
            weekly_manifest.json are the only durable state — no dated
            history snapshots are written (see module docstring).
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
    page_size: int = 0
    split_query: bool = False
    closed_date_field: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.canonical_path:
            self.canonical_path = f"data/live/{self.name}_current.csv"
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

    Does not write anything to disk — see write_canonical for that. Kept
    separate so the upsert logic is independently testable.
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


def write_canonical(config: DatasetConfig, merged_rows_by_id: dict[str, dict[str, Any]]) -> None:
    """Writes the upserted canonical file, atomically (temp file + rename —
    see _write_csv). This is the only file this module writes per dataset;
    weekly_manifest.json (written separately by write_manifest) is the
    other piece of durable state."""
    all_rows = list(merged_rows_by_id.values())
    _write_csv(config.canonical_path, config.columns, all_rows)


def run_dataset_refresh(
    config: DatasetConfig,
    app_token: str,
    run_date: Optional[date] = None,
    last_successful_run: Optional[str] = None,
) -> dict[str, Any]:
    """Runs the full refresh for one dataset: fetch, upsert, write the
    canonical file, and return this dataset's manifest entry.

    last_successful_run: the ISO date this dataset last completed
    successfully, as carried forward from the previously-committed
    manifest (see _last_successful_run_for) — None if it never has (a
    true first-ever run, or every prior run failed). Only used by
    split_query datasets, as the "new since" cutoff.

    Contract: this function NEVER raises. Any failure (network, HTTP, or
    decode) is caught here and converted into a manifest entry with status
    "failed" and an error message — this is what makes per-dataset failure
    isolation work at the call-site level (see run_all_datasets below),
    matching the per-dataset failure model in CLAUDE.md.

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
            new_since = (
                datetime.strptime(last_successful_run, "%Y-%m-%d").date()
                if last_successful_run
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

        write_canonical(config, existing)

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
            # Carried straight through unchanged — a failed run has no new
            # success to report, so it passes along whatever it was given.
            "last_successful_run": last_successful_run,
        }


def _read_manifest_if_exists(path: str) -> Optional[dict[str, Any]]:
    """Reads a previously-written manifest.json, if present. This is the
    only source of "last successful run" now that no local history files
    are written — it works on a fresh CI checkout precisely because the
    manifest (like the canonical CSVs) is committed to the repo each run,
    unlike anything written to local disk mid-run."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _last_successful_run_for(
    dataset_name: str, previous_manifest: Optional[dict[str, Any]]
) -> Optional[str]:
    """Determines one dataset's last successful run date from the
    previously-written manifest: that manifest's own run_date if this
    dataset succeeded then, or the last_successful_run it was already
    carrying forward if it had failed then too (chaining correctly through
    any number of consecutive failures). Returns None if there's no usable
    prior signal — a true first-ever run, or a dataset that has never
    succeeded."""
    if not previous_manifest:
        return None
    entry = previous_manifest.get("datasets", {}).get(dataset_name)
    if not entry:
        return None
    if entry.get("status") == "success":
        return previous_manifest.get("run_date")
    return entry.get("last_successful_run")


DEFAULT_MANIFEST_PATH = "data/live/weekly_manifest.json"


def run_all_datasets(
    configs: list[DatasetConfig],
    app_token: str,
    run_date: Optional[date] = None,
    manifest_path: str = DEFAULT_MANIFEST_PATH,
) -> dict[str, Any]:
    """Runs run_dataset_refresh for every config independently — one
    dataset's failure has no effect on another's execution, per the locked
    per-dataset failure model. Returns the full manifest dict, ready to be
    written to weekly_manifest.json as-is (with config.name as each dataset's
    key, matching CLAUDE.md's manifest schema).

    Reads the manifest still sitting at manifest_path from the *previous*
    run (if any) before building the new one, so each dataset's
    last_successful_run can be carried forward — see
    _last_successful_run_for. This read must happen before write_manifest
    overwrites that file, which is why it's done here rather than by the
    caller."""
    if run_date is None:
        run_date = date.today()

    previous_manifest = _read_manifest_if_exists(manifest_path)

    manifest: dict[str, Any] = {
        "run_date": run_date.isoformat(),
        "datasets": {},
    }

    for config in configs:
        last_successful_run = _last_successful_run_for(config.name, previous_manifest)
        manifest["datasets"][config.name] = run_dataset_refresh(
            config, app_token, run_date, last_successful_run=last_successful_run
        )

    return manifest


def write_manifest(manifest: dict[str, Any], path: str = DEFAULT_MANIFEST_PATH) -> None:
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
