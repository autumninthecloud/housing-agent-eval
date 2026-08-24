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

**Date:** Aug 24, '26
**Architecture:** Multi-agent (orchestrator + `data-cleaner`, `analyst`, `visualizer`, `narrator`, defined in `.claude/agents/`)
**Model:** `claude-sonnet-5` pinned in every subagent's frontmatter, verified via `/model` before each session; orchestrator session also pinned at launch
**Skills:** Enabled, same policy as single-agent; `/dataviz` invoked by the visualizer subagent

**Build note — two-session split (structural, not incidental):** creating new
subagent definitions and having the same session invoke them isn't possible —
Claude Code only scans `.claude/agents/` at session startup. This forced a
restart between authoring the four subagent files and running the pipeline,
splitting the build across two sessions. Unlike single-agent, this cost is
architectural, not accidental — the split is a genuine property of building a
multi-agent pipeline this way, not scaffolding to exclude.

**Cost — Part 1 (subagent authoring):** $0.3871 / 1m20s API / 2m37s wall
**Cost — Part 2 (pipeline execution):** $1.53 / 6m54s API / 11m7s wall
**Combined total:** $1.92 / 8m14s API / 13m44s wall
**Code changes:** 110 lines added (Part 1) + 392 lines added, 4 removed (Part 2)

**Outputs produced** (`outputs/multi_agent/`):
- `cleaned_violations.csv` + `data_cleaning_log.md` — data-cleaner's output
- `zip_stats.csv`, `top10.csv`, `trend_data.csv` — analyst's output, monthly granularity
- `charts/stacked_bar.png`, `charts/trend_line.png` — visualizer's output (trend line built as small multiples since 10 zips exceeds the 8-hue categorical palette)
- `narrative.md` — narrator's output

**Independence check:** the subagent-authoring session initially referenced
`scripts/pipeline.py` and `outputs/single_agent/` while exploring the repo
(see `lessons-learned.md`). The four subagent files were deleted and
re-authored with an explicit instruction not to reference single-agent's
work; the second attempt confirmed no single-agent files were opened.

**Data quality finding — corrupted postcode artifact, caught downstream:**
the top-ranked zip by strict Class C percentage, `02018`, has only 1 total
violation (100% Class C) — not a real signal. The analyst subagent identified
it as a likely corrupted-postcode artifact; the visualizer annotated it as a
"single-record artifact" in both charts rather than silently dropping it; the
narrator named it but correctly pivoted the substantive finding to the real
high-volume zips (10475, 10009, 10030, 10039, 10454), which show Class C
counts rising through 2025 and declining since late 2025/early 2026.

**Root cause of the artifact — a genuine spec-adherence failure, not a data
issue:** `data-cleaner.md`'s own specification required dropping any Postcode
outside the valid NYC range 10001–11697. What it actually implemented was a
**format normalizer, not a range validator** — cast to string, strip
non-digits, zero-pad to 5 digits — confirmed directly from its own
`data_cleaning_log.md`, which shows only 36 rows dropped (missing Postcode
only) versus single-agent's 49 (missing + malformed). A malformed value like
`2018` isn't rejected by that logic; it gets zero-padded into `02018`, a
syntactically valid-looking 5-digit string that passes a digit-count check
while remaining geographically nonsense. **The cleaning subagent's own
normalization step is what manufactured the corrupted value** that the
analyst subagent then had to catch — this isn't a silent omission, it's a
different (and insufficient) check substituted for the one specified.

**Notes:**
- Row-count comparison against single-agent (1,048,539 vs. 1,048,526) is what
  surfaced this — the 13-row gap exactly matches single-agent's
  malformed-postcode drop count, confirming multi-agent's cleaning stage
  did not perform that check.
- Analyst catching the artifact downstream, and narrator correctly not
  treating it as a real finding, is a genuine point in multi-agent's favor —
  a specialist stage caught and contained an upstream agent's mistake before
  it corrupted the headline result. Worth weighing this against the Data
  handling failure below when assessing overall reliability, not just netting
  them against each other.

#### Human score

| Section | Pass | Partial | Fail | Notes |
|---|---|---|---|---|
| Data handling | | | ✅ | data-cleaner's spec required dropping malformed Postcodes outside 10001–11697; it implemented a 5-digit format normalizer instead, which did not reject malformed values and actively produced the `02018` artifact rather than merely failing to catch it. This is a genuine deviation from the stated cleaning rule, not an unexplained drop |
| Top-10 table | | | ✅ | `02018` (1 total violation, fabricated 100% Class C) occupies rank 1, displacing a genuine result. Correctness failure in the table's core job, independent of downstream handling |
| Stacked bar chart | | ✅ | | Correctly executed its own spec (matches table scope, absolute counts, A/B/C stacked) and transparently annotated `02018` as a "single-record artifact" rather than presenting it as legitimate — but the artifact still occupies one of 10 bar positions. Chart faithfully rendered a corrupted upstream ranking; the corruption is the table's failure, not a charting-logic bug, so scored one notch above the outright Fails rather than identically |
| Trend line | | | ✅ | Two independent issues: (1) includes `02018` as one of the panels, same displacement problem as the table; (2) `analyst.md`'s own spec calls for showing only "the top 6 of the 10 ranked zips... kept to 6 for chart legibility" — this chart shows all 10 as small multiples, a direct deviation from the pipeline's own written spec, separate from the data-quality issue |
| Narrative | ✅ | | | Explicitly sets `02018` aside as a non-signal artifact, correctly identifies 10006 as the next real result, pivots to the volume-weighted zips (10475, 10009, 10030, 10039, 10454) with every number traceable to `top10.csv`/`trend_data.csv`, and appropriately caveats the partial final month. The one component that correctly contained the upstream failure rather than propagating it |

**Overall spec-match (human):** 1 / 4 core outputs fully passing (Narrative only; Top-10 table and Trend line Fail, Stacked bar chart Partial, Data handling — the prerequisite check — also Fail)

---

## Cross-architecture comparison

*(AI self-score and MAST-tagged failure modes still pending for multi-agent — fill in once the multi-agent AI self-score is complete.)*

| Metric | Single-agent | Multi-agent |
|---|---|---|
| Cost | $1.06 | $1.92 (Part 1: $0.3871 subagent authoring + Part 2: $1.53 pipeline execution — see note on forced session restart above) |
| Latency (API) | 4m 47s | 8m 14s (1m 20s + 6m 54s) |
| Latency (wall) | 8m 0s | 13m 44s (2m 37s + 11m 7s) |
| Spec-match (human) | 2 / 4 *(revised down from initial 4/4 after AI self-score review — see single-agent Agreement section)* | 1 / 4 |
| Spec-match (AI self-score) | 2 / 4 | ___ |
| Failure modes (MAST-tagged) | ___ | ___ |
