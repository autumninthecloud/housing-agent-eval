"""
insight_signals.py

Deterministic comparison logic for the insight agent. Per Phase 1's own
finding that agent reasoning is the expensive, error-prone part of the
pipeline, the percentage/delta arithmetic below runs here (cheap, testable,
no hallucination risk) rather than being left for the agent to compute
itself from raw stats.

diff_against_baseline() compares two stat dicts of the *same shape* — both
produced by socrata_pipeline.compute_baseline_stats, one for this run's
full current data, one being the dataset's permanent baseline_summary.json
entry — and surfaces category-mix shifts and zip newcomers worth a
sentence in the insight agent's narrative. Called from
socrata_pipeline.run_all_datasets, which has both stat dicts on hand
already; see CLAUDE.md's Phase 2 design for why there's no row-level
delta here (both datasets now do a full re-fetch every run, so there's no
persisted "last week's rows" to diff against).
"""

from __future__ import annotations

from typing import Any

# Minimum |delta| in percentage points before a category shift is worth
# surfacing in the narrative.
CATEGORY_DELTA_THRESHOLD_PTS = 5.0

# Cap on how many new top-15 zip entrants to report.
TOP_N_NEW_ZIP_ENTRANTS = 5


def _category_shifts(this_run: dict[str, Any], baseline: dict[str, Any]) -> list[dict[str, Any]]:
    shifts = []
    for field_name, week_breakdown in this_run.items():
        if not field_name.startswith("by_"):
            continue
        baseline_pct_by_value = {b["value"]: b["pct"] for b in baseline.get(field_name, [])}
        for item in week_breakdown:
            baseline_pct = baseline_pct_by_value.get(item["value"], 0.0)
            delta = round(item["pct"] - baseline_pct, 2)
            if abs(delta) >= CATEGORY_DELTA_THRESHOLD_PTS:
                shifts.append({
                    "field": field_name[3:],
                    "value": item["value"],
                    "this_run_pct": item["pct"],
                    "baseline_pct": baseline_pct,
                    "delta_pts": delta,
                })
    return shifts


def _new_zip_entrants(this_run: dict[str, Any], baseline: dict[str, Any]) -> list[dict[str, Any]]:
    if "top_zips_by_count" not in this_run or "top_zips_by_count" not in baseline:
        return []
    baseline_zips = {z["zip"] for z in baseline["top_zips_by_count"]}
    entrants = [z for z in this_run["top_zips_by_count"] if z["zip"] not in baseline_zips]
    return entrants[:TOP_N_NEW_ZIP_ENTRANTS]


def diff_against_baseline(this_run: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    """Compares this_run's stats (freshly computed from the current full
    dataset) against the dataset's fixed baseline entry. Both are
    compute_baseline_stats()-shaped dicts, so the comparison is symmetric
    and needs no per-dataset field-name knowledge."""
    return {
        "basis": (
            "this run's full aggregate stats (recomputed fresh every run) "
            "compared against the dataset's permanent baseline_summary.json entry"
        ),
        "category_shifts": _category_shifts(this_run, baseline),
        "new_zip_entrants": _new_zip_entrants(this_run, baseline),
        "total_count": {
            "this_run": this_run.get("total_count"),
            "baseline": baseline.get("total_count"),
        },
    }
