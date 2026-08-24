# Results — housing-agent-eval Phase 1

Run-by-run log of cost, latency, and rubric scores for the single-agent vs.
multi-agent comparison. See `rubric.md` for scoring criteria and
`lessons-learned.md` for the reasoning behind each methodology decision
referenced below.

---

## Run log

### Run: Single-agent, Phase 1, pinned (official baseline)

**Date:** Aug 24, '26
**Architecture:** Single-agent (`scripts/single_agent_pipeline.py`)
**Model:** `claude-sonnet-5`, pinned via `claude --model claude-sonnet-5`, verified with `/model` before the build prompt was sent
**Skills:** Enabled (per policy in `CLAUDE.md` — not stripped for artificial purity; see Lesson 8 in `lessons-learned.md`)

**Cost:** $0.75
**Latency (API duration — primary metric):** 3m 27s
**Latency (wall-clock — reference only):** 7m 9s
**Code changes:** 194 lines added, 21 removed
**Usage by model:**
- `claude-sonnet-5`: 552 input, 14.4k output, 1.5m cache read, 75.0k cache write ($0.74)
- `claude-haiku-4-5`: 2.0k input, 30 output, 0 cache read, 0 cache write ($0.0021) — via `/dataviz` skill, not session pinning (known exception, see `CLAUDE.md`)

**Permission prompts hit:** None

**Outputs produced** (`outputs/single_agent/`):
- `top10_zip_classC.csv` — top 10 zips by Class C %, top zip = 10006 at 60.0%
- `stacked_bar_by_zip.png` — A/B/C counts stacked, same 10 zips, sorted by Class C %
- `classC_trend_line.png` — monthly Class C counts per top-10 zip, Jan 2025–Aug 2026
- `narrative_summary.md` — grounded findings + trend description (rises to a peak in Feb 2026, then eases off — net +50.8% over the full window, not monotonic)
- `data_cleaning_log.md` — row counts through each cleaning step (36 missing zips, 13 malformed zips dropped; no date-filter drops since source file was already pre-filtered)

**Notes:**
- This is the second single-agent attempt. Run 1 (unpinned model, hit an encoding
  bug) is archived at `archive/run1-unpinned-single-agent/` and excluded from
  official results — see `lessons-learned.md` Lesson 7 for why.
- Comparison table between run 1 and this run is in `lessons-learned.md` Lesson 8.

#### Human score

| Section | Pass | Partial | Fail | Notes |
|---|---|---|---|---|
| Data handling | | | | |
| Top-10 table | | | | |
| Stacked bar chart | | | | |
| Trend line | | | | |
| Narrative | | | | |

**Overall spec-match (human):** ___ / 4 core outputs fully passing

#### AI self-score

*(Run in a fresh session, per `rubric.md` protocol — do not fill in until human
score above is complete.)*

| Section | Pass | Partial | Fail | Notes |
|---|---|---|---|---|
| Data handling | | | | |
| Top-10 table | | | | |
| Stacked bar chart | | | | |
| Trend line | | | | |
| Narrative | | | | |

**Overall spec-match (AI):** ___ / 4 core outputs fully passing

#### Agreement

| | |
|---|---|
| Sections where human and AI scores matched | ___ / 5 |
| Sections where they diverged, and how | ___ |
| Did the AI over-score or under-score itself relative to the human score? | ___ |

---

### Run: Multi-agent, Phase 1, pinned

*(Not yet run — placeholder for when the multi-agent pipeline is built.)*

---

## Cross-architecture comparison

*(Fill in once both architectures have a completed, scored run.)*

| Metric | Single-agent | Multi-agent |
|---|---|---|
| Cost | $0.75 | ___ |
| Latency (API) | 3m 27s | ___ |
| Spec-match (human) | ___ | ___ |
| Spec-match (AI self-score) | ___ | ___ |
| Failure modes (MAST-tagged) | ___ | ___ |
