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
- Both datasets always do a full rolling-window re-fetch every run — no
  persisted canonical file is required between runs for correctness. This
  was a deliberate reversal of an earlier 311-only incremental "split
  query" design: committing the canonical CSVs to git turned out to exceed
  GitHub's 100MiB per-file push limit (discovered when trying to push the
  first production bootstrap), and incremental upserting only works if the
  previous canonical file is available to merge into — which a fresh CI
  checkout never has anyway. See CLAUDE.md's Phase 2 design, "Pull
  strategy" and "Storage design" sections, for the full history.
- weekly_manifest.json stays small regardless of dataset size: no raw rows
  are ever embedded in it. Anomaly signals are computed by comparing this
  run's freshly-computed aggregate stats (compute_baseline_stats) against
  the dataset's permanent baseline_summary.json entry — see
  insight_signals.diff_against_baseline — not by diffing row-level deltas.
"""

from __future__ import annotations

import csv
import json
import os
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Callable, Optional

import insight_signals


SOCRATA_BASE_URL = "https://data.cityofnewyork.us/resource"
# Large filtered queries on the 311 dataset (28M+ rows) measured 267-350s for
# a single page regardless of $limit or $order — the WHERE filter itself is
# the fixed cost, not pagination. 600s gives real headroom above that.
REQUEST_TIMEOUT_SECONDS = 600
PAGE_SIZE = 5000  # SODA API page size per request; safely under typical caps

# A single throttled/transient page failure previously killed an entire
# dataset's run (no partial writes — see run_dataset_refresh), which on a
# ~33-page 311 pull meant one 429 anywhere in ~3 hours discarded all of it.
# Retry only 429 (rate limit) and 5xx (transient server-side) — a 4xx other
# than 429 (bad query, auth) will never succeed on retry, so it still fails
# fast. Respects a numeric Retry-After header when Socrata sends one.
MAX_FETCH_RETRIES = 5
RETRY_BACKOFF_BASE_SECONDS = 5.0

# Per-page retries alone don't bound a dataset's *total* retry spend: a
# token under sustained throttling could need a couple of retries on every
# single page without any one page ever hitting MAX_FETCH_RETRIES. 50 is
# well above what isolated, normal transient flakiness should cost across
# a ~33-36 page pull (a handful of 1-2-retry blips), so crossing it is a
# signal of systemic trouble worth aborting for, not a false alarm from an
# ordinary bad page or two.
MAX_TOTAL_RETRIES_PER_DATASET = 50


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
        canonical_path: where the upserted "current" CSV lives, local to
            the run — not committed to git (see module docstring). This is
            working state for this run only; weekly_manifest.json and
            baseline_summary.json are the durable, committed state.
        page_size: SODA API $limit per request. Defaults to the module-level
            PAGE_SIZE (0 means "use the default"). Large tables where the
            $where filter itself is the dominant cost should override this
            upward, since a bigger page amortizes that fixed per-query cost
            over more rows rather than paying it once per 5,000-row page.
        baseline_categorical_fields: columns to break down by count/pct in
            the one-time baseline summary (see compute_baseline_stats), e.g.
            ["class", "currentstatus"] for HPD. Each gets a "by_{field}"
            entry capped to the top 15 values by count.
        baseline_zip_field: column holding a zip code, for the baseline's
            "top zips by count" entry. None skips that entry.
        baseline_concentration_field / baseline_concentration_value: an
            optional (field, value) pair — e.g. ("class", "C") for HPD —
            used to compute "top zips by {field}={value} concentration" in
            the baseline, mirroring Phase 1's own Class C ranking
            methodology. Both must be set together, or both left None.
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
    baseline_categorical_fields: list[str] = field(default_factory=list)
    baseline_zip_field: Optional[str] = None
    baseline_concentration_field: Optional[str] = None
    baseline_concentration_value: Optional[str] = None

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
        if bool(self.baseline_concentration_field) != bool(self.baseline_concentration_value):
            raise ValueError(
                f"baseline_concentration_field and baseline_concentration_value "
                f"must be set together for dataset {self.name!r}."
            )


class DatasetRefreshError(Exception):
    """Raised internally when a pull fails. Always caught within
    run_dataset_refresh — callers should never see this; they get a
    manifest entry with status 'failed' instead. Kept as a real exception
    (not silently swallowed deeper in the call stack) so the specific
    failure point is easy to find in tests or interactive debugging.
    """


class DeadlineExceededError(DatasetRefreshError):
    """Raised when the script-wide deadline (see run_dataset_refresh's
    `deadline` param) is checked and found already passed — either between
    pages, before a retry sleep, or before a dataset's fetch has even
    started. Subclasses DatasetRefreshError so existing failure handling
    (run_dataset_refresh's except block) catches it with no special-casing;
    only the message distinguishes it from an actual network/HTTP error."""


class RetryBudgetExceededError(DatasetRefreshError):
    """Raised when a single dataset's fetch has consumed more than
    MAX_TOTAL_RETRIES_PER_DATASET retries across all its pages combined —
    see _RetryBudget. Distinguishes "this dataset is under sustained,
    systemic trouble" from an isolated page hitting its own per-page cap."""


class _RetryBudget:
    """Tracks total retries spent across every page of one dataset's
    fetch_all_rows call (as opposed to MAX_FETCH_RETRIES, which bounds a
    single page in isolation). consume() is called once per retry attempt,
    right before the backoff sleep — the same checkpoint used for the
    deadline check, since both exist to interrupt "about to retry anyway"
    rather than an in-flight request."""

    def __init__(self, limit: int = MAX_TOTAL_RETRIES_PER_DATASET) -> None:
        self.used = 0
        self.limit = limit

    def consume(self, dataset_name: str) -> None:
        self.used += 1
        if self.used > self.limit:
            raise RetryBudgetExceededError(
                f"Dataset {dataset_name!r} exceeded its total retry budget "
                f"({self.limit} retries across all pages) this run — "
                f"treating this as sustained/systemic trouble rather than "
                f"continuing to retry."
            )


def _check_before_retry(
    dataset_name: str,
    deadline: Optional[float],
    retry_budget: Optional[_RetryBudget],
) -> None:
    """Called at every "about to sleep and retry" point in _fetch_page,
    before the sleep — checking here (rather than only between pages)
    means a dataset stuck retrying a single page still gets interrupted
    promptly instead of free-riding on MAX_FETCH_RETRIES' own ~63-minute
    worst-case budget. Raises DeadlineExceededError or
    RetryBudgetExceededError; does nothing if both checks pass."""
    if deadline is not None and time.monotonic() >= deadline:
        raise DeadlineExceededError(
            f"Dataset {dataset_name!r} hit the script-wide deadline while "
            f"mid-retry on a page fetch."
        )
    if retry_budget is not None:
        retry_budget.consume(dataset_name)


def _build_soql_where(config: DatasetConfig, since: date) -> str:
    """Builds the $where clause: date-window filter, optionally ANDed with
    an extra filter (e.g. 311's agency = 'HPD')."""
    since_str = since.strftime("%Y-%m-%dT00:00:00")
    clause = f"{config.date_field} >= '{since_str}'"
    if config.extra_where:
        clause = f"({clause}) AND ({config.extra_where})"
    return clause


def _retry_delay_seconds(attempt: int, retry_after_header: Optional[str]) -> float:
    """Delay before the next fetch retry. Honors a numeric Retry-After
    header if Socrata sends one (rate-limit responses often do); otherwise
    falls back to exponential backoff from RETRY_BACKOFF_BASE_SECONDS."""
    if retry_after_header is not None:
        try:
            return max(float(retry_after_header), 0.0)
        except ValueError:
            pass
    return RETRY_BACKOFF_BASE_SECONDS * (2**attempt)


def _fetch_page(
    config: DatasetConfig,
    where_clause: str,
    offset: int,
    app_token: str,
    deadline: Optional[float] = None,
    retry_budget: Optional[_RetryBudget] = None,
) -> list[dict[str, Any]]:
    """Fetches a single page of rows from the SODA API. Raises
    DatasetRefreshError on any HTTP or JSON-decoding failure — callers should
    not need to inspect urllib exceptions directly.

    deadline (a time.monotonic() timestamp) and retry_budget are checked
    right before every retry sleep below (_check_before_retry) — not
    during an in-flight request, which can't be interrupted mid-urlopen.
    Both are optional so this function still works standalone/in tests."""
    params = {
        "$select": ",".join(config.columns),
        "$where": where_clause,
        "$limit": str(config.page_size),
        "$offset": str(offset),
        "$order": config.id_field,
    }
    url = f"{SOCRATA_BASE_URL}/{config.dataset_id}.json?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url, headers={"X-App-Token": app_token})

    attempt = 0
    while True:
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                body = response.read()
            break
        except urllib.error.HTTPError as exc:
            transient = exc.code == 429 or exc.code >= 500
            if not transient or attempt >= MAX_FETCH_RETRIES:
                raise DatasetRefreshError(
                    f"HTTP {exc.code} from Socrata for dataset {config.name!r} "
                    f"(offset={offset}): {exc.reason}"
                ) from exc
            _check_before_retry(config.name, deadline, retry_budget)
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            delay = _retry_delay_seconds(attempt, retry_after)
            time.sleep(delay)
            attempt += 1
        except urllib.error.URLError as exc:
            if attempt >= MAX_FETCH_RETRIES:
                raise DatasetRefreshError(
                    f"Network error reaching Socrata for dataset {config.name!r} "
                    f"(offset={offset}): {exc.reason}"
                ) from exc
            _check_before_retry(config.name, deadline, retry_budget)
            time.sleep(_retry_delay_seconds(attempt, None))
            attempt += 1
        except (socket.timeout, TimeoutError) as exc:
            # urlopen only wraps OSErrors raised while sending the request into
            # URLError; a timeout while reading the response (h.getresponse())
            # propagates unwrapped, so it needs its own handler here to honor
            # run_dataset_refresh's "never raises past this module" contract.
            if attempt >= MAX_FETCH_RETRIES:
                raise DatasetRefreshError(
                    f"Timed out reaching Socrata for dataset {config.name!r} "
                    f"(offset={offset}) after {REQUEST_TIMEOUT_SECONDS}s"
                ) from exc
            _check_before_retry(config.name, deadline, retry_budget)
            time.sleep(_retry_delay_seconds(attempt, None))
            attempt += 1
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as exc:
            # Same "propagates unwrapped from h.getresponse()" issue as the
            # timeout case above, but for the remote host dropping the
            # connection mid-response rather than a timeout — hit directly
            # against the live HPD endpoint during the first bootstrap run.
            if attempt >= MAX_FETCH_RETRIES:
                raise DatasetRefreshError(
                    f"Connection reset by Socrata for dataset {config.name!r} "
                    f"(offset={offset}): {exc}"
                ) from exc
            _check_before_retry(config.name, deadline, retry_budget)
            time.sleep(_retry_delay_seconds(attempt, None))
            attempt += 1

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise DatasetRefreshError(
            f"Could not decode JSON from Socrata for dataset {config.name!r} "
            f"(offset={offset}): {exc}"
        ) from exc


def fetch_all_rows(
    config: DatasetConfig,
    where_clause: str,
    app_token: str,
    deadline: Optional[float] = None,
    retry_budget: Optional[_RetryBudget] = None,
) -> list[dict[str, Any]]:
    """Fetches every row matching where_clause, paging through the SODA API
    until a short page signals the end. Raises DatasetRefreshError if any
    page fails — this is intentional: a partial fetch must not be treated as
    a complete one, since that would corrupt the upsert (see module
    docstring on per-dataset atomicity).

    Checks `deadline` between pages (in addition to _fetch_page's own
    before-every-retry-sleep check) so a dataset that's fetching cleanly,
    just slowly, still gets interrupted at a page boundary rather than
    running unbounded. retry_budget is shared across every page of this
    call — see _RetryBudget."""
    all_rows: list[dict[str, Any]] = []
    offset = 0

    while True:
        if deadline is not None and time.monotonic() >= deadline:
            raise DeadlineExceededError(
                f"Dataset {config.name!r} hit the script-wide deadline "
                f"between pages (offset={offset}, {len(all_rows)} rows "
                f"fetched so far this call)."
            )
        page = _fetch_page(config, where_clause, offset, app_token, deadline, retry_budget)
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
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Merges freshly-fetched rows into the existing canonical file's rows.

    Returns (new_rows, updated_rows, merged_existing):
        new_rows: rows whose ID was not previously in the canonical file.
        updated_rows: rows whose ID existed before and whose content changed.
            Rows that were re-fetched but are byte-for-byte identical to what
            was already on disk are NOT included here — the manifest should
            reflect real change, not just "the API returned this ID again".
        merged_existing: the full post-merge row set, keyed by ID — exactly
            what write_canonical should write. Handed back rather than
            rebuilt by the caller: an earlier version had run_dataset_refresh
            redundantly re-read the canonical file and re-normalize every
            fetched row a second time "for clarity", which doubled peak
            memory on a multi-million-row full-window pull and caused an
            OOM kill partway through HPD's first bootstrap run.

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

    return new_rows, updated_rows, existing


def write_canonical(config: DatasetConfig, merged_rows_by_id: dict[str, dict[str, Any]]) -> None:
    """Writes the upserted canonical file, atomically (temp file + rename —
    see _write_csv). This is the only file this module writes per dataset;
    weekly_manifest.json (written separately by write_manifest) and
    baseline_summary.json (written separately by
    write_baseline_entry_if_missing) are the other durable state."""
    all_rows = list(merged_rows_by_id.values())
    _write_csv(config.canonical_path, config.columns, all_rows)


DEFAULT_BASELINE_PATH = "data/live/baseline_summary.json"


def compute_baseline_stats(config: DatasetConfig, run_date: date) -> dict[str, Any]:
    """Computes small, bounded aggregate stats (not raw rows) from a
    dataset's canonical file, for the one-time baseline summary — see
    write_baseline_entry_if_missing. Reads the canonical CSV directly
    rather than being passed rows in memory, so it always reflects the
    full current upserted state.

    Deliberately capped and aggregate-only: total count, top-15 breakdowns
    by each of config.baseline_categorical_fields, top-15 zips by count
    (if baseline_zip_field is set), and top-15 zips by concentration of one
    field=value (if baseline_concentration_field/_value are set) — sized
    to stay tiny (a few KB) regardless of how large the canonical file
    grows, unlike embedding raw rows."""
    rows = list(_read_canonical_csv(config.canonical_path, config.columns).values())
    total = len(rows)

    stats: dict[str, Any] = {
        "generated_at": run_date.isoformat(),
        "total_count": total,
    }

    for field_name in config.baseline_categorical_fields:
        counts: dict[str, int] = {}
        for row in rows:
            value = row.get(field_name) or "(blank)"
            counts[value] = counts.get(value, 0) + 1
        top = sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:15]
        stats[f"by_{field_name}"] = [
            {"value": value, "count": count, "pct": round(100 * count / total, 2) if total else 0}
            for value, count in top
        ]

    if config.baseline_zip_field:
        zip_counts: dict[str, int] = {}
        for row in rows:
            z = row.get(config.baseline_zip_field) or "(blank)"
            zip_counts[z] = zip_counts.get(z, 0) + 1
        top_zips = sorted(zip_counts.items(), key=lambda kv: kv[1], reverse=True)[:15]
        stats["top_zips_by_count"] = [{"zip": z, "count": count} for z, count in top_zips]

    if config.baseline_concentration_field and config.baseline_zip_field:
        target_field = config.baseline_concentration_field
        target_value = config.baseline_concentration_value
        zip_total: dict[str, int] = {}
        zip_target: dict[str, int] = {}
        for row in rows:
            z = row.get(config.baseline_zip_field) or "(blank)"
            zip_total[z] = zip_total.get(z, 0) + 1
            if row.get(target_field) == target_value:
                zip_target[z] = zip_target.get(z, 0) + 1
        # Zips with very few total rows produce noisy 100%-style concentrations
        # that aren't meaningful signal — require a minimum sample size.
        concentrations = [
            {
                "zip": z,
                "target_count": zip_target.get(z, 0),
                "total_count": zip_total[z],
                "target_pct": round(100 * zip_target.get(z, 0) / zip_total[z], 2),
            }
            for z in zip_total
            if zip_total[z] >= 5
        ]
        concentrations.sort(key=lambda d: d["target_pct"], reverse=True)
        stats["top_zips_by_target_concentration"] = {
            "field": target_field,
            "value": target_value,
            "zips": concentrations[:15],
        }

    return stats


def write_baseline_entry_if_missing(
    config: DatasetConfig, run_date: date, baseline_path: str = DEFAULT_BASELINE_PATH
) -> None:
    """Writes this dataset's baseline aggregate entry into baseline_path,
    but only if it doesn't already have one — the baseline is meant to
    capture the starting point once and never move, so an existing entry
    for this dataset is left untouched. Merges into whatever's already in
    the file rather than overwriting other datasets' entries, so each
    dataset's baseline can be captured on whichever run first has data for
    it (they don't need to succeed on the same run)."""
    baseline = _read_json_if_exists(baseline_path) or {}
    if config.name in baseline:
        return
    baseline[config.name] = compute_baseline_stats(config, run_date)
    os.makedirs(os.path.dirname(baseline_path) or ".", exist_ok=True)
    tmp_path = f"{baseline_path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2)
    os.replace(tmp_path, baseline_path)


def run_dataset_refresh(
    config: DatasetConfig,
    app_token: str,
    run_date: Optional[date] = None,
    last_successful_run: Optional[str] = None,
    deadline: Optional[float] = None,
) -> dict[str, Any]:
    """Runs the full refresh for one dataset: fetch the entire rolling
    window fresh, upsert into whatever canonical file happens to exist
    locally (empty on a fresh CI checkout — see module docstring), write
    it back out, and return this dataset's manifest entry.

    last_successful_run: the ISO date this dataset last completed
    successfully, as carried forward from the previously-committed
    manifest (see _last_successful_run_for). Not used for querying — kept
    only to pass through unchanged on failure, so a failed run's manifest
    entry still reports how stale the dataset is.

    deadline: an absolute time.monotonic() timestamp this dataset's fetch
    must finish by. Checked up front (covers the case where a prior
    dataset in the same run already used up the whole budget — this
    dataset never even starts) and then threaded through fetch_all_rows/
    _fetch_page, which check it between pages and before retry sleeps.
    None means no deadline (e.g. ad hoc local runs). A fresh _RetryBudget
    is created per call, scoped to just this one dataset's fetch.

    Contract: this function NEVER raises. Any failure (network, HTTP,
    decode, deadline, or retry-budget exhaustion) is caught here and
    converted into a manifest entry with status "failed" and an error
    message — this is what makes per-dataset failure isolation work at the
    call-site level (see run_all_datasets below), matching the per-dataset
    failure model in CLAUDE.md. Crucially, this means a dataset that times
    out or exhausts its retry budget still produces a normal "failed"
    manifest entry via write_manifest, rather than losing the whole run's
    results to an external hard-kill — see CLAUDE.md's "Refresh script
    behavior" for why that distinction matters.
    """
    if run_date is None:
        run_date = date.today()
    window_since = run_date - timedelta(days=config.window_days)

    try:
        if deadline is not None and time.monotonic() >= deadline:
            raise DeadlineExceededError(
                f"Dataset {config.name!r} never started — the script-wide "
                f"deadline was already passed before this dataset's turn "
                f"(likely because an earlier dataset in the same run used "
                f"the whole budget)."
            )

        retry_budget = _RetryBudget()
        where_clause = _build_soql_where(config, window_since)
        fetched_rows = fetch_all_rows(config, where_clause, app_token, deadline, retry_budget)

        _, _, existing = upsert_rows(config, fetched_rows)
        del fetched_rows  # large full-window pull; free before writing

        write_canonical(config, existing)

        return {
            "status": "success",
            "total_current": len(existing),
            # Lets the insight agent (and anyone reading the manifest)
            # tell a short test window apart from a real run without
            # guessing — see insight-agent.md's "check window_days first"
            # instruction.
            "window_days": config.window_days,
            "window_start": window_since.isoformat(),
            "window_end": run_date.isoformat(),
        }

    except DatasetRefreshError as exc:
        return {
            "status": "failed",
            "error": str(exc),
            # Carried straight through unchanged — a failed run has no new
            # success to report, so it passes along whatever it was given.
            "last_successful_run": last_successful_run,
            "window_days": config.window_days,
        }


def _read_json_if_exists(path: str) -> Optional[dict[str, Any]]:
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
    baseline_path: str = DEFAULT_BASELINE_PATH,
    deadline: Optional[float] = None,
) -> dict[str, Any]:
    """Runs run_dataset_refresh for every config independently — one
    dataset's failure has no effect on another's execution, per the locked
    per-dataset failure model. Returns the full manifest dict, ready to be
    written to weekly_manifest.json as-is (with config.name as each dataset's
    key, matching CLAUDE.md's manifest schema).

    deadline: an absolute time.monotonic() timestamp shared across every
    config in this call — passed straight through to run_dataset_refresh,
    which checks it up front for each dataset in turn. When multiple
    configs are passed (the local/manual "run everything" mode), this is
    a single budget for the whole sequential run: if an earlier dataset
    eats the whole budget, later ones correctly get a "never started"
    failed entry instead of silently being skipped with no record. In the
    split-per-dataset-job CI mode, each job calls this with exactly one
    config and its own job-specific deadline.

    Reads the manifest still sitting at manifest_path from the *previous*
    run (if any) before building the new one, so each dataset's
    last_successful_run can be carried forward — see
    _last_successful_run_for. This read must happen before write_manifest
    overwrites that file, which is why it's done here rather than by the
    caller.

    Also reads baseline_path's contents once, before any dataset runs
    (`baseline_before`), so a dataset that gets its baseline written for
    the first time *this* run is correctly treated as having nothing to
    compare against yet, rather than being diffed against the baseline
    that was just captured from this same run's own data (see
    insight_signals.diff_against_baseline).

    For each dataset that succeeds and already had a baseline entry
    before this run, attaches a "signals" key (this run's aggregate stats
    vs. that baseline) to its manifest entry. Then calls
    write_baseline_entry_if_missing — a no-op for any dataset that already
    has a baseline entry, so this only actually writes anything the first
    time a given dataset has data."""
    if run_date is None:
        run_date = date.today()

    previous_manifest = _read_json_if_exists(manifest_path)
    baseline_before = _read_json_if_exists(baseline_path) or {}

    manifest: dict[str, Any] = {
        "run_date": run_date.isoformat(),
        "datasets": {},
    }

    for config in configs:
        last_successful_run = _last_successful_run_for(config.name, previous_manifest)
        result = run_dataset_refresh(
            config,
            app_token,
            run_date,
            last_successful_run=last_successful_run,
            deadline=deadline,
        )
        manifest["datasets"][config.name] = result

        if result["status"] == "success":
            baseline_entry_before = baseline_before.get(config.name)
            if baseline_entry_before:
                this_run_stats = compute_baseline_stats(config, run_date)
                result["signals"] = insight_signals.diff_against_baseline(
                    this_run_stats, baseline_entry_before
                )
            write_baseline_entry_if_missing(config, run_date, baseline_path)

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
