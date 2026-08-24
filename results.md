# Results — housing-agent-eval Phase 1

Run-by-run log of cost, latency, and rubric scores for the single-agent vs.
multi-agent comparison. See `rubric.md` for scoring criteria and
`lessons-learned.md` for the reasoning behind each methodology decision
referenced below.

**Methodology note — one-shot scoring:** each architecture is scored from a
single official run, not an average across repeated attempts. This is a known
limitation, not an oversight: run-to-run variance was directly observed during
Phase 1 prep (three single-agent attempts, same pinned model and prompt,
produced noticeably different depths of data-quality scrutiny — see
`lessons-learned.md`, Lesson 11). The numbers below represent what one attempt
at each architecture produced, not a characterization of either architecture's
typical or average reliability. Both architectures are held to the same
one-shot standard for consistency.

---

## Run log

### Run: Single-agent, Phase 1, pinned — ARCHIVED, NOT OFFICIAL

**Status:** Archived. Do not use these numbers as the Phase 1 single-agent
baseline. See `lessons-learned.md`, Lesson 9, for full explanation.

**Why archived:** after this build completed and was initially logged below, the
`/dataviz` skill was accidentally invoked in the same session (typing `/dataviz`
to inspect its frontmatter actually ran it), which modified the chart outputs and
narrative in place. This was valuable — it caught a real trend-line bug — but it
means the outputs on disk are no longer the clean, reproducible pinned baseline,
and the combined session cost ($1.74 total) conflates a deliberate build with an
accidental editing pass. Outputs and pipeline script archived to
`archive/run2-accidental-dataviz-invocation/`.

**Original build-only numbers (before the accidental invocation):**
**Cost:** $0.75 · **Latency (API):** 3m 27s · **Latency (wall):** 7m 9s

**Accidental `/dataviz` invocation, isolated:**
**Cost:** ~$0.99 · **Latency (API):** ~8m 02s · **Latency (wall):** ~27m 44s

**Combined session total:** $1.74 · 11m 29s API · 34m 53s wall

---

### Run: Single-agent, Phase 1, pinned (official baseline — one-shot)

**Date:** Aug 24, '26
**Architecture:** Single-agent (`scripts/pipeline.py`)
**Model:** `claude-sonnet-5`, pinned via `claude --model claude-sonnet-5`, verified with `/model` before the build prompt was sent
**Skills:** Enabled (per policy in `CLAUDE.md`); `/dataviz` invoked as part of the deliberate build this time, not accidentally

**Cost:** $1.06
**Latency (API duration — primary metric):** 4m 47s
**Latency (wall-clock — reference only):** 8m 0s
**Code changes:** 351 lines added, 9 removed
**Usage by model:**
- `claude-sonnet-5`: 560 input, 25.6k output, 2.0m cache read, 99.3k cache write ($1.06)
- `claude-haiku-4-5`: 2.0k input, 30 output, 0 cache read, 0 cache write ($0.0021) — via `/dataviz` skill (known exception, see `CLAUDE.md`)

**Permission prompts hit:** None reported

**Outputs produced** (`outputs/single_agent/`):
- `top10_zip_classC.csv` — top 10 zips by Class C %, top result at 60.0%
- `stacked_bar_by_class.png` — A/B/C stacked counts for the top 10
- `trend_class_c_top_zips.png` — monthly Class C counts, top 6 of the 10 ranked zips, full series shown
- `narrative_summary.md` — grounded claims only; states a mixed trend (3 up / 3 down) rather than a uniform direction
- `data_notes.md` — full cleaning log and judgment calls, including two flagged data-quality issues (below)

**Data-quality issues caught and documented (not silently absorbed):**
1. Raw row count (1,048,575) lands exactly at Excel's row-export limit — flagged
   as a possible-truncation concern in `data_notes.md`, not treated as a
   confirmed defect since it can't be verified either way from this file alone.
2. Citywide violation counts for Feb–May 2025 run at ~10–30% of every other
   month, then spike in June 2025 — a data-completeness gap, not a real dip. A
   naive first-half/second-half trend split would have shown nearly every zip as
   "increasing" purely from this artifact. Trend direction was instead computed
   over the stable post-Aug-2025 window; the chart still shows the full series
   so the gap remains visible and auditable. Zip 10006's own trend call was
   additionally flagged as low-confidence (only 90 total violations, one spike
   month deciding its direction).

**Notes:**
- This is the third single-agent attempt. Run 1 (unpinned, encoding bug) is
  archived — see Lesson 7. Run 2 (pinned, then accidentally modified by a skill
  invocation) is archived above — see Lessons 8-10.
- Neither run 1 nor run 2 caught either data-quality issue above, despite
  identical raw input — confirmed by comparing archived `data_notes.md`
  (run 1) and `data_cleaning_log.md` (run 2) directly. See Lesson 11.
- Per the one-shot methodology note at the top of this file, this run — not an
  average of all three attempts — is the official Phase 1 single-agent result.

#### Human score

| Section | Pass | Partial | Fail | Notes |
|---|---|---|---|---|
| Data handling | ✅ | | | |
| Top-10 table | | ✅ | | *(Updated after AI self-score review, see Agreement below)* Math/grouping/ranking correct, but an unstated ≥50-violation minimum-sample filter was applied before ranking — well-reasoned (documented in `data_notes.md`) but not part of the rubric's stated ranking method |
| Stacked bar chart | ✅ | | | Data is correct; zips not sorted in ascending/descending order, and some bar segments are hard to read — legibility issue, not a correctness issue |
| Trend line | | ✅ | | *(Updated after AI self-score review, see Agreement below)* Narrative's up/down calls rely on judgment calls not visible on the chart itself: Aug 2026 partial month excluded from the trend but not from the plot, up/down direction computed only from Aug 2025 onward, and 10006's direction flagged as low-confidence off a single-month spike. Fails the rubric's "checkable from the chart alone" criterion in multiple places, not just one |
| Narrative | ✅ | | | |

**Overall spec-match (human):** 2 / 4 core outputs fully passing *(revised down from an initial 4/4 after verifying the AI self-score's catches against `data_notes.md` — both held up)*

#### AI self-score

*(Run in a fresh session, per `rubric.md` protocol — do not fill in until human
score above is complete.)*

| Section | Pass | Partial | Fail | Notes |
|---|---|---|---|---|
| Data handling | ✅ | | | Source/field/filter correct; drops reconcile exactly |
| Top-10 table | | ✅ | | Math/grouping/ranking metric all correct, but the pipeline quietly applied an unstated ≥50-violation minimum-sample filter before ranking (documented in `data_notes.md`, but not part of the rubric spec) |
| Stacked bar chart | ✅ | | | No caveat noted |
| Trend line | | ✅ | | Chart plots the full series, but the narrative's up/down calls use a "stable window" not visible on the chart — at least zip 10009's "down" call isn't verifiable from the chart alone, per the checkability criterion |
| Narrative | ✅ | | | Fully grounded in the table, answers the core question, appropriately concise |

**Overall spec-match (AI):** 2 / 4 core outputs fully passing

#### Agreement

| | |
|---|---|
| Sections where human and AI scores matched | 5 / 5, after verification *(initially 3/5 — see history below)* |
| Sections where they diverged, and how | **Initial divergence, before verification:** human scored Top-10 table and Trend line as Pass; AI self-score flagged both as Partial, citing an undocumented ≥50-violation ranking filter and multiple chart-unverifiable narrative claims respectively. Checked both against `data_notes.md` directly — both AI catches held up exactly as described. Human score updated to match. **Stacked bar chart:** both ultimately scored Pass, but for different reasons — human caught a visual legibility/ordering issue the AI didn't mention (likely because reviewing chart-generation code doesn't surface how the rendered image actually reads); AI's Pass had no caveat attached at all |
| Did the AI over-score or under-score itself relative to the human score? | **Under-scored relative to the human's *initial* pass** (2/4 vs. an initial 4/4) — and correctly so. The human's first pass missed two real, verifiable issues that the AI caught by reading `data_notes.md` more carefully than the human did on the first read. This is the more interesting and less commonly discussed failure mode: not the AI grading itself generously, but the *human* grader missing real problems that were sitting in plain sight in the pipeline's own documentation. The AI, in this instance, was the more reliable grader on two of five sections — while the human still caught something the AI missed entirely (the chart legibility issue), which only a visual read of the rendered output would surface |

---

### Run: Multi-agent, Phase 1, pinned (one-shot)

*(Not yet run — placeholder for when the multi-agent pipeline is built. Same
one-shot methodology applies: this will be scored from a single run, not an
average across attempts, for consistency with the single-agent baseline above.)*

---

## Cross-architecture comparison

*(Fill in once both architectures have a completed, scored run.)*

| Metric | Single-agent | Multi-agent |
|---|---|---|
| Cost | $1.06 | ___ |
| Latency (API) | 4m 47s | ___ |
| Spec-match (human) | ___ | ___ |
| Spec-match (AI self-score) | ___ | ___ |
| Failure modes (MAST-tagged) | ___ | ___ |
