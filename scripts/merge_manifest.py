"""
merge_manifest.py

Combines the per-dataset partial results produced by running
refresh_weekly.py --dataset {hpd,311} in separate CI jobs into one
weekly_manifest.json, and merges each job's (possibly baseline-updated)
copy of baseline_summary.json into one file.

Why this exists: splitting HPD and 311 into separate GitHub Actions jobs
(so one dataset's job-level timeout can't take the other's already-
completed result down with it — see CLAUDE.md's "Refresh script behavior")
means there's no longer a single process that naturally produces one
combined manifest. This script is the "finalize" step that puts the two
jobs' outputs back together, and runs regardless of whether either
upstream job succeeded, failed cleanly, or never produced output at all
(hit its own GitHub-level timeout before `refresh_weekly.py`'s in-script
deadline could fire) — see CLAUDE.md's Phase 2 design for the per-dataset
failure model this preserves.

Usage:
    python scripts/merge_manifest.py \\
        --expected hpd 311 \\
        --partial data/live/partial_manifest_hpd.json \\
        --partial data/live/partial_manifest_311.json \\
        --baseline data/live/baseline_summary_hpd.json \\
        --baseline data/live/baseline_summary_311.json \\
        --previous-manifest data/live/weekly_manifest.json

A dataset named in --expected but with no matching entry among the
--partial files (because its job's artifact never got uploaded, most
likely a GitHub-level job timeout) gets a synthesized "failed" entry here,
with last_successful_run chained forward from --previous-manifest so
staleness tracking doesn't silently break.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from typing import Any, Optional

from socrata_pipeline import _last_successful_run_for, _read_json_if_exists


def _write_json_atomic(path: str, data: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, path)


def merge_manifests(
    expected_datasets: list[str],
    partial_paths: list[str],
    previous_manifest_path: Optional[str],
) -> dict[str, Any]:
    """Builds the combined manifest from however many partials actually
    exist. Missing datasets (named in expected_datasets but absent from
    every partial) get a synthesized failed entry rather than being
    silently omitted — an omission would look identical to "this dataset
    doesn't exist" to the insight agent, instead of "its job didn't
    report in this run"."""
    previous_manifest = _read_json_if_exists(previous_manifest_path) if previous_manifest_path else None

    found: dict[str, Any] = {}
    run_date = None
    for path in partial_paths:
        partial = _read_json_if_exists(path)
        if not partial:
            continue
        if run_date is None:
            run_date = partial.get("run_date")
        found.update(partial.get("datasets", {}))

    if run_date is None:
        run_date = date.today().isoformat()

    for dataset_name in expected_datasets:
        if dataset_name in found:
            continue
        found[dataset_name] = {
            "status": "failed",
            "error": (
                "No partial manifest found for this dataset this run — its "
                "job most likely hit GitHub's own job-level timeout before "
                "refresh_weekly.py's in-script deadline could fire and "
                "write a result, or its artifact upload failed."
            ),
            "last_successful_run": _last_successful_run_for(dataset_name, previous_manifest),
        }

    return {"run_date": run_date, "datasets": found}


def merge_baselines(baseline_paths: list[str]) -> dict[str, Any]:
    """Each path is one job's local copy of baseline_summary.json —
    starting from the same pre-run committed file, with at most that
    job's own dataset key added (write_baseline_entry_if_missing is a
    no-op for a dataset that already has an entry). A plain union across
    all copies is therefore safe: any key present in more than one copy
    is identical content, not a real conflict."""
    merged: dict[str, Any] = {}
    for path in baseline_paths:
        data = _read_json_if_exists(path)
        if data:
            merged.update(data)
    return merged


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected", nargs="+", required=True)
    parser.add_argument("--partial", dest="partials", action="append", default=[])
    parser.add_argument("--baseline", dest="baselines", action="append", default=[])
    parser.add_argument("--previous-manifest", default=None)
    parser.add_argument("--manifest-output", default="data/live/weekly_manifest.json")
    parser.add_argument("--baseline-output", default="data/live/baseline_summary.json")
    args = parser.parse_args(argv)

    manifest = merge_manifests(args.expected, args.partials, args.previous_manifest)
    _write_json_atomic(args.manifest_output, manifest)

    baseline = merge_baselines(args.baselines)
    if baseline:
        _write_json_atomic(args.baseline_output, baseline)

    any_success = any(
        entry.get("status") == "success" for entry in manifest["datasets"].values()
    )
    for name, entry in manifest["datasets"].items():
        if entry.get("status") == "success":
            print(f"[{name}] merged: success")
        else:
            print(f"[{name}] merged: FAILED — {entry.get('error')}", file=sys.stderr)

    return 0 if any_success else 1


if __name__ == "__main__":
    sys.exit(main())
