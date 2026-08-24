# Evaluation Rubric — housing-agent-eval Phase 1

Used to score both the single-agent and multi-agent pipeline outputs against the same
fixed criteria, so the comparison isolates architecture as the only variable.

Score each item **Pass / Partial / Fail**. Partial and Fail require a one-line note
explaining what was wrong — these notes feed directly into `failure-analysis.md`.

Log the completed rubric for each run in `results.md`, alongside that run's `/cost`
output and total wall-clock time.

---

## 1. Data handling

| Check | Pass criteria |
|---|---|
| Correct source file | Used `data/static/` as-is, did not re-derive, re-fetch, or modify the dataset |
| Correct date field | Filtered/sorted using `NOVIssuedDate`, not `CurrentStatusDate` or any other date column |
| Correct date filter | Only records with `NOVIssuedDate ≥ 2025-01-01` included |
| No silent drops | Row count in the final analysis is explainable (e.g. matches filtered input row count, or any exclusions are stated) |

## 2. Top-10 zip code table

| Check | Pass criteria |
|---|---|
| Correct ranking metric | Ranked by Class C violations as a **percentage of each zip's total violations**, not raw Class C count |
| Correct grouping | Aggregated by `Postcode`, not by `Borough` or `NTA` |
| Correct math | Spot-check 2–3 rows: Class C % = (Class C count / total violations) for that zip |
| Table is complete | Shows exactly 10 rows, each with zip code, Class C %, and enough context (e.g. total violation count) to sanity-check the ranking |

## 3. Stacked bar chart (violation counts by class, per zip)

| Check | Pass criteria |
|---|---|
| Correct axes | X-axis = zip code, Y-axis = violation count |
| Correct stacking | Bars stacked by Class A/B/C, not summed into a single bar or shown as separate charts |
| Correct scope | Covers the same top zip codes as the table (or is explicit about which zips it covers, if different) |
| Absolute counts, not percentages | Chart shows raw counts for context, distinct from the percentage-based ranking in the table |

## 4. Trend line (Class C violations over time, top zip codes)

| Check | Pass criteria |
|---|---|
| Correct field | Time axis uses `NOVIssuedDate` |
| Correct scope | Covers Class C violations only, for the top-ranked zip codes (not all zips, not all classes) |
| Reasonable granularity | Time buckets (e.g. weekly/monthly) are legible and not so coarse/fine that the trend is unreadable |
| Trend direction is checkable | A reader could verify "increasing" or "decreasing" from the chart alone, without needing the narrative to explain it |

## 5. Narrative summary

| Check | Pass criteria |
|---|---|
| Grounded in the data | Every specific claim (a number, a zip code, a direction of change) traces back to the table/charts above — no invented or unverifiable claims |
| Answers the core question | Explicitly states which zips have the highest Class C concentration and whether that concentration is trending up or down |
| Appropriately short | Summary is a short narrative, not a restatement of the full table |

## 6. Process metrics (captured regardless of pass/fail above)

| Metric | How to capture |
|---|---|
| Cost | `/cost` output immediately after the run, pasted into `results.md` |
| Latency | Total wall-clock time for the run *(note: `/cost` reports both "Total duration (API)" and "Total duration (wall)" — wall time includes any time spent sitting on permission prompts. For architecture comparisons, prefer logging API duration alongside wall-clock, since wall-clock is affected by how long you personally took to approve prompts, not by the pipeline itself)* |
| Failure mode(s) | If any check above is Partial/Fail, tag it using the MAST taxonomy category it best fits (e.g. spec deviation, verification failure, inter-agent misalignment) |

---

## Scoring summary (fill in per run)

Score this rubric **twice per run, independently**: once by you (human), once by
Claude self-scoring its own output. Do your human pass first, before reading or
requesting the AI's self-score, to avoid anchoring your judgment to it.

**Run:** _______________  (e.g. "Single-agent, Phase 1, run 1")
**Date:** _______________

### Human score

| Section | Pass | Partial | Fail | Notes |
|---|---|---|---|---|
| Data handling | | | | |
| Top-10 table | | | | |
| Stacked bar chart | | | | |
| Trend line | | | | |
| Narrative | | | | |

**Overall spec-match (human):** ___ / 4 core outputs fully passing

### AI self-score

Run in a fresh session (or at minimum, after the pipeline's `/cost` has already
been captured — see note below), using the identical rubric and the same prompt
wording across both architectures.

| Section | Pass | Partial | Fail | Notes |
|---|---|---|---|---|
| Data handling | | | | |
| Top-10 table | | | | |
| Stacked bar chart | | | | |
| Trend line | | | | |
| Narrative | | | | |

**Overall spec-match (AI):** ___ / 4 core outputs fully passing

### Agreement

| | |
|---|---|
| Sections where human and AI scores matched | ___ / 5 |
| Sections where they diverged, and how | ___ |
| Did the AI over-score or under-score itself relative to the human score? | ___ |

### Process metrics

**Pipeline cost (build only, captured via `/cost` before any self-scoring):** $___
**Self-scoring cost (if logged separately):** $___
**Latency (pipeline build, wall-clock):** ___
**Latency (pipeline build, API duration — see note in Process metrics table above; prefer this for architecture comparisons):** ___
**Failure modes observed (MAST-tagged):** ___