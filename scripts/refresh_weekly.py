"""
refresh_weekly.py

Entry point for the Phase 2 weekly refresh. Defines the HPD and 311 dataset
configs per CLAUDE.md's locked design, runs both independently via
socrata_pipeline.run_all_datasets, and writes the manifest the insight agent
reads.

Usage:
    python scripts/refresh_weekly.py

Requires NYC_OPEN_DATA_APP_TOKEN to be set in the environment (a GitHub
Actions repository secret when run in CI; export it locally for manual runs).

Exit codes:
    0 - manifest written, at least one dataset succeeded
    1 - manifest written, but every dataset failed this run
    2 - could not even get as far as running (e.g. missing app token)
"""

import sys

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
    split_query=True,
    closed_date_field="closed_date",
)


def main() -> int:
    try:
        app_token = get_app_token()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    manifest = run_all_datasets([HPD_CONFIG, COMPLAINTS_311_CONFIG], app_token)
    write_manifest(manifest)

    any_success = False
    for dataset_name, entry in manifest["datasets"].items():
        status = entry["status"]
        if status == "success":
            any_success = True
            print(
                f"[{dataset_name}] success: "
                f"{entry['new_count']} new, {entry['updated_count']} updated, "
                f"{entry['total_current']} total"
            )
        else:
            print(
                f"[{dataset_name}] FAILED: {entry['error']} "
                f"(last successful run: {entry.get('last_successful_run') or 'never'})",
                file=sys.stderr,
            )

    if not any_success:
        print("ERROR: every dataset failed this run.", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
