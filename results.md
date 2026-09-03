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
| Trend line | | | ✅ | `02018` (fabricated, single-record) occupies one of the 10 panels in a chart whose purpose is showing trend direction for the top-ranked zips. Unlike the stacked bar chart, where the artifact is one labeled bar among nine legitimate ones, here it corrupts the chart's core premise — one of "the 10 zips that matter" isn't a real zip at all. Displacing a genuine result from a top-10 trend view is a correctness failure, not just a presentation quirk. *(Note: an earlier draft of this reasoning cited a "top 6 of 10" requirement from `analyst.md` — that requirement was in an earlier, contaminated draft of the file that was deleted and rewritten; the actual governing `analyst.md` and `visualizer.md` correctly permit all 10 zips as small multiples, confirmed independently by the AI self-score below. That citation was a documentation error, not a real spec deviation, and has been removed. The Fail stands on the `02018` displacement issue alone.)* |
| Narrative | ✅ | | | Explicitly sets `02018` aside as a non-signal artifact, correctly identifies 10006 as the next real result, pivots to the volume-weighted zips (10475, 10009, 10030, 10039, 10454) with every number traceable to `top10.csv`/`trend_data.csv`, and appropriately caveats the partial final month. The one component that correctly contained the upstream failure rather than propagating it |

**Overall spec-match (human):** 1 / 4 core outputs fully passing (Narrative only; Top-10 table and Trend line Fail, Stacked bar chart Partial, Data handling — the prerequisite check — also Fail)

#### AI self-score

*(Scored independently in a fresh subagent session with no access to the human
score above or to `results.md` at all — only `rubric.md`, the files in
`outputs/multi_agent/`, and the subagent specs in `.claude/agents/`, per
`rubric.md` protocol.)*

| Section | Pass | Partial | Fail | Notes |
|---|---|---|---|---|
| Data handling | ✅ | | | Source used as-is; `NOVIssuedDate` correctly used; row-count arithmetic (1,048,575 − 36 = 1,048,539) verified exactly against actual file line count |
| Top-10 table | | ✅ | | Ranking metric, grouping (Postcode), and math all verified correct (spot-checked 02018=100%, 10006=60.0%, 10475=39.7222% — all match). But no minimum-volume threshold on the ranking lets tiny-n rows dominate: rank #1 is `02018` with a single record and a "02" prefix that isn't a valid NYC zip at all (likely a corrupted postcode that passed the cleaner's 5-digit format check without a plausibility check); `10005` (n=25) and `10006` (n=90) also rank ahead of any real high-volume zip. Table format is spec-compliant but practically misleading without that caveat baked in |
| Stacked bar chart | ✅ | | | Correct axes, correct A/B/C stacking, same 10 zips as the table, absolute counts. Explicitly annotates 02018 as a "single-record artifact" — good transparency |
| Trend line | ✅ | | | Monthly buckets (`NOVIssuedDate`-derived `Period`), Class C only, all 10 top zips shown (small-multiples with independent y-scales, explicitly justified in the subtitle per visualizer.md's allowance). Rise-then-decline shape is visually checkable per panel without narrative support |
| Narrative | ✅ | | | Every number spot-checked against `trend_data.csv`/`top10.csv` matched exactly (e.g., 10454 peak 306 in 2025-12, end value 42 in 2026-08 — both confirmed). Correctly deprioritizes the low-N artifact rows in favor of high-volume zips, answers the core question, and flags the partial-month caveat for 2026-08 rather than overclaiming |

**Overall spec-match (AI):** 3 / 4 core outputs fully passing

**Self-scoring session cost (logged separately, per `rubric.md`'s process-metrics
convention — not part of the pipeline build cost above, and not counted in the
Cross-architecture comparison table below):** $0.76 / 3m 15s API / 14m 30s wall.
This includes the cost of the top-level session's protocol-violation
self-correction (spawning an isolated sub-agent after accidentally reading
`results.md`) and the independent verification that `visualizer.md` permits all
10 zips in the trend line — the check that resolved the mistaken "top 6"
citation elsewhere in this document. Worth noting: verifying the AI's own
scoring integrity cost more than either half of the original subagent-authoring
session ($0.3871), which is itself a small data point on the overhead of
rigorous self-assessment.

**Reasoning for the one Partial:** The Top-10 table's four rubric sub-checks (ranking metric, grouping, math, completeness) all literally pass, but an independent data-quality check found `02018` is not a valid NYC postcode and has n=1, yet ranks #1 by the stated methodology; `10005`/`10006` are legitimate but statistically thin. Downstream agents (visualizer, narrator) both compensated by flagging/deprioritizing it, but the table itself — the actual rubric deliverable — has no such safeguard. Failure mode tag: verification failure (missing plausibility/minimum-N check before finalizing the ranked table).

#### Agreement

| | |
|---|---|
| Sections where human and AI scores matched | 2 / 5 (Stacked bar chart — both credited its transparent `02018` annotation; Narrative — both Pass, both independently verified its numbers trace back to `top10.csv`/`trend_data.csv`) |
| Sections where they diverged, and how | **Data handling:** human Fail vs. AI Pass — the AI's own spot-check verified the row-count arithmetic (1,048,575 − 36 = 1,048,539) but did not check that arithmetic *against what the spec required*: `data-cleaner.md` mandated a 10001–11697 range check, and the AI accepted the file's normalizer-based approach without noticing it doesn't perform that check. Confirming the math is internally consistent is not the same as confirming the pipeline did what it was told to do — a real gap in this self-score, not a difference of judgment. **Top-10 table:** human Fail vs. AI Partial — both agree `02018` is a real, disqualifying-caliber problem (the AI's own language — "not a valid NYC postcode," "practically misleading" — is nearly as strong as the human's Fail reasoning), but land on different severities. The AI's own failure-mode tag ("verification failure... before finalizing the ranked table") arguably supports a Fail as much as a Partial; worth treating this specific gap as more a threshold disagreement than a substantive one. **Trend line:** human Fail vs. AI Pass — the AI correctly confirmed showing all 10 zips is spec-compliant (this AI self-score itself is what caught and corrected the mistaken "top 6" citation in this document, per the note above), but its Pass reasoning focuses entirely on the chart's technical execution and doesn't weigh the `02018` displacement issue at all, unlike its own Top-10 table review, which did |
| Did the AI over-score or under-score itself relative to the human score? | **Over-scored relative to the human** (3/4 vs. 1/4) — the reverse direction from the single-agent comparison (where the AI under-scored itself, 2/4 vs. human's initial 4/4). Notably, the AI's own reasoning text is often *more* critical in substance than its final Pass/Partial verdict reflects — e.g. calling the table "practically misleading" while still marking it Partial, or independently confirming a genuine spec violation (Trend line's all-10-zips display) while treating a different, arguably more severe spec-relevant issue (`02018`'s presence) as not disqualifying. This suggests the divergence isn't just "the AI missed things" — in Data handling it did, but in Top-10 table and Trend line, the AI largely *saw* the same problems the human did and still scored more leniently, indicating a threshold/severity-calibration gap rather than a detection gap in those two cases specifically |

---

## MAST-taxonomy failure-mode tagging (full pass)

Tags below are assigned against the **human score** (the rubric's authoritative
score for the headline comparison table). AI self-score divergences are noted
where the disagreement is itself informative, but are not separately MAST-tagged
as pipeline failures — see the standalone scoring-process note at the end of
this section.

MAST categories used: **Specification** (agent deviates from, ignores, or
under-specifies the task), **Inter-Agent Misalignment** (breakdown in how
agents coordinate, hand off, or rely on each other), **Task Verification**
(no agent checks a deliverable's correctness/plausibility before it's treated
as final).

### Single-agent

| Section | Score | MAST category | Reasoning |
|---|---|---|---|
| Top-10 table | Partial | **Specification** | An unstated ≥50-violation minimum-sample filter was applied before ranking. The filter is well-reasoned and documented in `data_notes.md`, but it silently substitutes the agent's own ranking criterion for the one the rubric/spec actually defines. Same category as multi-agent's Data handling failure below — an agent substituting a different rule than the one it was given — but caught and contained by the same agent in the same pass, not propagated. |
| Trend line | Partial | **Task Verification** | The narrative's up/down calls depend on judgment calls invisible in the chart itself (stable-window cutoff starting Aug 2025, Aug 2026 partial-month exclusion, 10006's single-spike-driven direction). No check was made that the deliverable satisfies the rubric's own "checkable from the chart alone" criterion before calling the trend line complete. |

Single-agent has no Inter-Agent Misalignment tag — there's only one agent,
so this category structurally doesn't apply. This absence is itself worth
noting for the cross-architecture comparison: single-agent's two failures are
both individual-agent failures, with no coordination layer to fail at.

### Multi-agent

| Section | Score | MAST category | Reasoning |
|---|---|---|---|
| Data handling | Fail | **Specification** | `data-cleaner.md`'s spec required a 10001–11697 range validator; the subagent implemented a 5-digit format normalizer instead. This is the root cause of the `02018` artifact — not a missed edge case, but a different (and insufficient) check substituted for the one specified. Root of the causal chain below. |
| Top-10 table | Fail | **Task Verification** *(downstream of Data handling, same causal chain)* | Independent of the cleaning-stage spec failure, the ranking step itself has no plausibility or minimum-N check before finalizing rank #1. Even granting the malformed input, a verification step here (n=1, geographically implausible prefix) could have caught what the cleaning stage missed. This is why it's tagged separately from Data handling rather than folded into it — it's a distinct missing safeguard, one stage later. |
| Trend line | Fail | **Task Verification** *(downstream of Data handling, same causal chain)* | Same artifact, one stage further downstream, corrupting a different deliverable's core premise (one of "the 10 zips that matter" isn't real). Not a new failure mechanism — the same missing plausibility check that should have stopped the artifact at the Top-10 table stage would also have stopped it here. Listed separately only because it's a separately-scored rubric deliverable, not because it's a separately-caused failure. |
| Stacked bar chart | Partial | *(no new failure — containment, not failure)* | The visualizer correctly executed its own spec against corrupted upstream input and transparently labeled the artifact rather than presenting it as legitimate. This is the one deliverable where an agent's behavior actively reduced harm from the upstream failure rather than propagating or being blind to it. Scored Partial only because the artifact still physically occupies a bar position, not because the visualizer did anything wrong. |
| — | — | **Inter-Agent Misalignment** *(system-level, not tied to one rubric row)* | The analyst identified `02018` as a likely artifact and the narrator correctly excluded it from the substantive finding — but neither fed that judgment back upstream or into the Top-10 table deliverable itself, which remains uncorrected on disk. The system has an agent that *knows* the ranking is wrong (analyst's own reasoning) and an agent that *acts on that knowledge narratively* (narrator), but no mechanism routes that knowledge back into fixing or flagging the table artifact, which is the actual rubric deliverable being scored. This is a coordination gap distinct from any single agent's spec deviation — a fix for Data handling's Specification failure would prevent this instance, but wouldn't close the general gap: nothing in this pipeline's design routes a downstream agent's correction back to an upstream deliverable. |

**Causal chain visualization:**

```
data-cleaner (Specification failure)
  → normalizer accepts "2018" → zero-pads to "02018"
      → analyst (Task Verification gap: no plausibility/min-N check)
          → 02018 ranks #1 in Top-10 table [FAIL]
              → 02018 occupies a panel in Trend line [FAIL]
              → 02018 occupies a bar in Stacked bar chart [Partial — contained via annotation]
          → analyst's own reasoning correctly flags 02018 as an artifact,
            but that correction never reaches the Top-10 table itself
            [Inter-Agent Misalignment]
              → narrator correctly excludes it from the narrative [Pass —
                contained via correct downstream judgment, same gap as above]
```

### Cross-architecture failure-mode comparison

| MAST category | Single-agent | Multi-agent |
|---|---|---|
| Specification | 1 (Top-10 table — contained within the same pass) | 1 (Data handling — root cause of a 3-deliverable chain) |
| Task Verification | 1 (Trend line) | 2 (Top-10 table, Trend line — both downstream of the same root cause) |
| Inter-Agent Misalignment | N/A (single agent) | 1 (correction generated but not routed back to the deliverable) |
| Total failing/partial deliverables | 2 / 4 | 4 / 4 (incl. 1 contained) |

**Note on severity vs. count:** raw counts favor single-agent, but count alone
understates the difference in kind. Single-agent's two failures are
independent — a bad filter and a bad chart-verification gap, unrelated to each
other. Multi-agent's four are almost entirely one root-cause failure
propagating through a pipeline with no mechanism to route a downstream
correction back upstream — architecturally, the interesting failure here
isn't "the data-cleaner made a mistake" (single agents make mistakes too,
see single-agent's own Top-10 table row) but that **the system had the
information needed to prevent the Top-10 table failure (the analyst's own
correct diagnosis) and no structural way to use it.** That gap — not the
original data-cleaner bug — is the multi-agent-specific finding worth
carrying into Phase 3's governance-audit skill: a "delegation logging" or
"override point" control that let a downstream agent's flag actually amend
an upstream deliverable would have prevented 2 of the 3 propagated failures
outright.

### Scoring-process note (not a pipeline failure — logged separately)

The human/AI self-score Agreement sections above surface a pattern worth
keeping distinct from the pipeline MAST tags: in the multi-agent self-score,
the AI's own reasoning text was frequently as critical as the human's (e.g.
calling the Top-10 table "practically misleading," independently confirming
the `02018` displacement in the Trend line) while its Pass/Partial verdicts
were consistently more lenient than that reasoning implied. This is a
**severity-calibration gap in the scoring process itself**, not a pipeline
failure mode, and doesn't get a MAST tag — but it's directly relevant to
Phase 3, where the same self-scoring pattern could show up in the
governance-audit skill's own outputs and would be worth checking for.

---

## Cross-architecture comparison

| Metric | Single-agent | Multi-agent |
|---|---|---|
| Cost | $1.06 | $1.92 (Part 1: $0.3871 subagent authoring + Part 2: $1.53 pipeline execution — see note on forced session restart above) |
| Latency (API) | 4m 47s | 8m 14s (1m 20s + 6m 54s) |
| Latency (wall) | 8m 0s | 13m 44s (2m 37s + 11m 7s) |
| Spec-match (human) | 2 / 4 *(revised down from initial 4/4 after AI self-score review — see single-agent Agreement section)* | 1 / 4 |
| Spec-match (AI self-score) | 2 / 4 | 3 / 4 |
| Failure modes (MAST-tagged) | Specification (Top-10 table), Task Verification (Trend line) — see full MAST-taxonomy tagging section above | Specification (Data handling, root cause), Task Verification (Top-10 table, Trend line — downstream), Inter-Agent Misalignment (correction not routed back to deliverable) — see full MAST-taxonomy tagging section above |
