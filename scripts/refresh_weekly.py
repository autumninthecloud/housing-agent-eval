"""
refresh_weekly.py

Entry point for the Phase 2 weekly refresh. Defines the HPD and 311 dataset
configs per CLAUDE.md's locked design and runs them via
socrata_pipeline.run_all_datasets.

Both datasets do a full rolling-window re-fetch every run (see CLAUDE.md's
Phase 2 design, "Pull strategy" — 311 previously used an incremental
split-query optimization, reversed once committing the canonical CSVs
turned out to exceed GitHub's per-file push limit). Nothing needs to
persist between runs for correctness; the canonical CSVs under
data/live/*.csv are local working files for this run only, not committed.

Two modes:

- No --dataset flag (default): runs both datasets sequentially in one
  process and writes the full combined weekly_manifest.json. This is the
  original, simplest shape — kept for local/manual runs. A single shared
  deadline (DEFAULT_COMBINED_DEADLINE_MINUTES) covers both datasets, so an
  earlier dataset using up the whole budget correctly produces a "never
  started" failure for a later one instead of silently skipping it.

- --dataset {hpd,311}: runs just that one dataset and writes ONLY its
  manifest entry to --output (a partial file, not the canonical
  weekly_manifest.json). This is what the GitHub Actions workflow uses —
  one job per dataset, each with its own timeout-minutes and its own
  in-script --deadline-minutes, so one dataset's platform-level job
  timeout can never take the other dataset's already-completed result
  down with it. scripts/merge_manifest.py combines the partials
  afterward. baseline_summary.json is still read/written at its usual
  path either way (run_all_datasets handles that regardless of how many
  configs it's given) — a split-mode job's caller is responsible for
  collecting that file too.

Usage:
    python scripts/refresh_weekly.py
    python scripts/refresh_weekly.py --dataset hpd --deadline-minutes 120 \
        --output data/live/partial_manifest_hpd.json
    python scripts/refresh_weekly.py --dataset 311 --deadline-minutes 270 \
        --output data/live/partial_manifest_311.json

Requires NYC_OPEN_DATA_APP_TOKEN to be set in the environment (a GitHub
Actions repository secret when run in CI; export it locally for manual runs).

Exit codes (scoped to whichever dataset(s) this invocation ran):
    0 - manifest/partial written, at least one dataset succeeded
    1 - manifest/partial written, but every dataset run here failed
    2 - could not even get as far as running (e.g. missing app token)
"""

from __future__ import annotations

import argparse
import sys
import time

from socrata_pipeline import (
    DatasetConfig,
    get_app_token,
    run_all_datasets,
    write_manifest,
)


HPD_CONFIG = DatasetConfig(
    name="hpd",
    dataset_id="wvxf-dwi5",
    id_field="violationid",
    date_field="novissueddate",
    columns=[
        "violationid",
        "boroid",
        "zip",
        "latitude",
        "longitude",
        "class",
        "novissueddate",
        "currentstatus",
        "currentstatusdate",
    ],
    extra_where=None,
    window_days=365,
    canonical_path="data/live/hpd_violations_current.csv",
    page_size=50000,
    baseline_categorical_fields=["class", "currentstatus"],
    baseline_zip_field="zip",
    baseline_concentration_field="class",
    baseline_concentration_value="C",
)

COMPLAINTS_311_CONFIG = DatasetConfig(
    name="311",
    dataset_id="erm2-nwe9",
    id_field="unique_key",
    date_field="created_date",
    columns=[
        "unique_key",
        "agency",
        "complaint_type",
        "descriptor",
        "borough",
        "incident_zip",
        "latitude",
        "longitude",
        "created_date",
        "closed_date",
        "status",
    ],
    extra_where="agency = 'HPD'",
    window_days=365,
    canonical_path="data/live/311_complaints_current.csv",
    page_size=50000,
    baseline_categorical_fields=["status", "complaint_type"],
    baseline_zip_field="incident_zip",
)

CONFIGS_BY_NAME = {"hpd": HPD_CONFIG, "311": COMPLAINTS_311_CONFIG}

# Per-dataset deadlines for split (CI) mode, matched to each dataset's own
# expected workload (see CLAUDE.md's "Refresh script behavior" for the
# worst-case-runtime math): HPD's smaller table normally finishes in
# ~40min, 311's in ~165-190min. Only used as the --deadline-minutes
# default if that flag is omitted; the workflow passes it explicitly.
DEFAULT_DEADLINE_MINUTES_BY_DATASET = {"hpd": 120, "311": 270}

# Single shared deadline for the default (no --dataset) combined mode —
# covers both datasets run sequentially in one process.
DEFAULT_COMBINED_DEADLINE_MINUTES = 320


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset",
        choices=sorted(CONFIGS_BY_NAME),
        default=None,
        help="Run only this dataset and write a partial manifest to --output "
        "instead of the combined weekly_manifest.json. Omit to run both.",
    )
    parser.add_argument(
        "--deadline-minutes",
        type=float,
        default=None,
        help="Script-wide deadline in minutes. Defaults depend on mode: "
        "per-dataset default from DEFAULT_DEADLINE_MINUTES_BY_DATASET when "
        "--dataset is given, DEFAULT_COMBINED_DEADLINE_MINUTES otherwise.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Where to write this run's result. Only meaningful with "
        "--dataset; defaults to data/live/partial_manifest_{dataset}.json.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] = None) -> int:
    args = parse_args(argv if argv is not None else sys.argv[1:])

    try:
        app_token = get_app_token()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.dataset:
        configs = [CONFIGS_BY_NAME[args.dataset]]
        deadline_minutes = (
            args.deadline_minutes
            if args.deadline_minutes is not None
            else DEFAULT_DEADLINE_MINUTES_BY_DATASET[args.dataset]
        )
        output_path = args.output or f"data/live/partial_manifest_{args.dataset}.json"
    else:
        configs = [HPD_CONFIG, COMPLAINTS_311_CONFIG]
        deadline_minutes = (
            args.deadline_minutes
            if args.deadline_minutes is not None
            else DEFAULT_COMBINED_DEADLINE_MINUTES
        )
        output_path = None  # writes the combined canonical manifest instead

    deadline = time.monotonic() + deadline_minutes * 60
    manifest = run_all_datasets(configs, app_token, deadline=deadline)

    if output_path:
        write_manifest(manifest, output_path)
    else:
        write_manifest(manifest)

    any_success = False
    for dataset_name, entry in manifest["datasets"].items():
        status = entry["status"]
        if status == "success":
            any_success = True
            signals_note = (
                " (signals vs. baseline computed)"
                if "signals" in entry
                else " (no baseline yet to compare against — this run's stats become the baseline)"
            )
            print(f"[{dataset_name}] success: {entry['total_current']} total{signals_note}")
        else:
            print(
                f"[{dataset_name}] FAILED: {entry['error']} "
                f"(last successful run: {entry.get('last_successful_run') or 'never'})",
                file=sys.stderr,
            )

    if not any_success:
        print("ERROR: every dataset run here failed.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
