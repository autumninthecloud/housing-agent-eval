# housing-agent-eval

Experimenting with single- vs multi-agent LLM workflows on housing safety BI tasks, plus a governance audit skill that evaluates cost, reliability, and NIST-aligned controls.

## Project overview

This repo contains a three-phase project:

1. **Phase 1 – Controlled experiment (static NYC data):**
   Build the same housing-safety BI task twice in Claude Code:
   - A single-agent pipeline (one agent does everything sequentially).
   - A multi-agent pipeline (orchestrator + specialist subagents).

   Compare cost, latency, accuracy/spec match, and failure modes using the MAST multi-agent failure taxonomy.

2. **Phase 2 – Live weekly pipeline (NYC data):**
   Use NYC HPD housing violations and 311 housing complaints via NYC Open Data as a live feed.
   - A deterministic script recomputes aggregates from a full-window pull every week.
   - A lightweight "insight agent" runs on top to flag anomalies and generate short narratives.

3. **Phase 3 – Governance audit:**
   A governance-audit skill scores both architectures against agentic gaps in NIST AI RMF (autonomy tiers, tool scoping, delegation logging, override/kill switches), and is wired into a weekly GitHub Action.

## Data

- **Static dataset (Phase 1):** NYC Housing Maintenance Code Violations, filtered to NOVIssuedDate ≥ 2025-01-01 (CSV export, stored under `data/static/`). Columns retained: `ViolationID`, `Borough`, `Postcode`, `Class`, `NOVIssuedDate`. All other source columns (`NOVDescription`, `CurrentStatus`, `CurrentStatusDate`, `ViolationStatus`, `RentImpairing`, `Latitude`, `Longitude`, `NTA`, `NOVID`) were dropped to reduce file size; none are used by the ranking, chart, or trend calculations defined above. This trimmed schema applies only to the Phase 1 static file and must stay fixed for the duration of the single-agent vs. multi-agent comparison — do not modify columns mid-experiment.
- **Live datasets (Phase 2):** see the Phase 2 design summary below and `CLAUDE.md`'s Phase 2 design section for full detail (datasets, schema, storage design). Column set is not restricted to the Phase 1 schema.

## Core experiment question

> Which NYC zip codes have the highest concentration of hazardous (Class C) violations issued since January 1, 2025, and are those concentrations increasing or decreasing over that period?

Ranking is based on Class C violations as a percentage of each zip code's total violations; the stacked bar chart shows absolute counts by class (A/B/C) for context. Both the single-agent and multi-agent pipelines answer this using the same static dataset and the same ranking definition, so architecture is the only variable.

## Model configuration

The primary single-agent vs. multi-agent comparison pins both to `claude-sonnet-5`,
so architecture is the only variable — see `CLAUDE.md` for the exact pinning setup.

A secondary sub-experiment holds architecture constant (multi-agent only) and
varies model selection instead: multi-agent pinned to Sonnet vs. multi-agent left
free to auto-route per subagent. This tests whether per-task model routing is a
genuine efficiency advantage of the multi-agent architecture, isolated from the
primary result rather than folded into it.

**Verification protocol:** before every run (both architectures), confirm the
pinned model is actually active by running `/model` in the Claude Code session.
`/model` is a local CLI command — it reads session config only, makes no API call,
and adds no cost or latency to the run. This is the standardized check used
instead of asking Claude to read/summarize CLAUDE.md's model configuration, since
that alternative would consume tokens and add an inconsistent amount of cost
depending on how it's phrased each time.

## Results summary (Phase 1 complete)

Both architectures were built, run once each (see `results.md` for the
one-shot methodology note), and scored against `rubric.md` — once by a human
reviewer, once by an AI self-score in an isolated session, per the dual-scoring
protocol below.

| Metric | Single-agent | Multi-agent |
|---|---|---|
| Cost | $1.06 | $1.92 (includes a forced session-restart cost unique to multi-agent — see `lessons-learned.md`) |
| Latency (API) | 4m 47s | 8m 14s |
| Spec-match (human) | 2 / 4 | 1 / 4 |
| Spec-match (AI self-score) | 2 / 4 | 3 / 4 |

Multi-agent came in more expensive, slower, and lower-scoring on this one-shot
comparison — the opposite of what multi-agent architectures are often assumed
to deliver. The root cause traced to a single subagent (`data-cleaner`)
implementing a different, weaker check than the one specified in its own
frontmatter, which manufactured a corrupted data point that propagated into
the final ranking. Full detail, including where human and AI scoring diverged
and why, is in `results.md`; the methodology decisions behind how this
comparison was kept fair are in `lessons-learned.md`.

A full MAST-taxonomy failure-mode tagging pass across both architectures is
also complete — see `results.md`'s "MAST-taxonomy failure-mode tagging"
section for per-section tags, the causal chain behind multi-agent's
propagated failures, and the cross-architecture failure-mode comparison.

## Phase 2 design summary (locked, pre-implementation)

Full detail in `CLAUDE.md`'s Phase 2 design section. Summary:

**Not a re-run of Phase 1's architecture comparison.** The weekly refresh is
a deterministic script (no LLM); the insight agent is a single agent, not
orchestrator + subagents. Phase 1's finding that multi-agent's only
structural edge (a subagent catching another's mistake) doesn't transfer to
a single lightweight anomaly/narrative step supported this default.

**Datasets:**
- HPD Housing Maintenance Code Violations (`wvxf-dwi5`) — same source as
  Phase 1, pulled live.
- 311 Service Requests from 2020 to Present (`erm2-nwe9`), filtered to
  `agency = 'HPD'` for the housing-complaint subset. Not a separate
  dataset — the citywide 311 feed, filtered.

Both are **mutable** (existing records get status updates, not just new
rows), confirmed against each dataset's field documentation. Storage is
upsert-by-ID into a canonical current file — not append-only — specifically
to avoid the duplicate-row corruption a naive append design would cause on a
mutable feed. These canonical files are **local working state only, never
committed to git** — see below for why — and no dated history archive is
kept either, for the same underlying reason: at real measured row counts a
history snapshot would add ~180-190MB per dataset to the repo *every single
run*, indefinitely.

**Rolling 12-month window**, computed dynamically each run, replacing
Phase 1's fixed 2025-01-01 cutoff — appropriate for a one-time static
comparison, wrong for an ongoing live pipeline where a fixed cutoff would
dilute anomaly detection with stale cases.

**Handoff:** the refresh script writes `weekly_manifest.json`, which the
insight agent reads instead of the full canonical files. It never embeds
raw rows — anomaly arithmetic is computed from small aggregate stats
(this run's vs. the dataset's permanent `baseline_summary.json`) instead.
The agent only runs if the manifest has at least one successful dataset.

**Both datasets do a full re-fetch every run — no incremental pull.** This
reverses an earlier 311-only optimization (two smaller queries per week
instead of one full 365-day pull, cutting ~3 hours down to ~10-15 minutes)
that was built, tested, and then reversed: it depended on last week's full
canonical file being available to upsert into, and that file turned out to
be too large to commit to git at all (~124MB for 311, over GitHub's 100MiB
per-file push limit) — found when trying to push the first production
bootstrap. Keeping the optimization alive would have meant standing up
storage for that file outside git (Release assets, external blob storage);
accepting 311's ~3-hour runtime instead — a free, uncapped, nobody's-
waiting-on-it scheduled job — was the simpler fix, and it removes the need
for any persisted state between runs entirely. Full numbers, the original
split-query design, and a rejected `:updated_at` approach are kept as
historical record in `CLAUDE.md`'s Phase 2 design section.

**Infra:** GitHub Actions cron (public repo, free, uncapped) with a
concurrency group so a manual `workflow_dispatch` queues behind rather
than cancels an in-progress scheduled run, NYC Open Data app token stored
as a GitHub Actions secret (never committed). HPD and 311 run as separate
jobs, each with its own in-script deadline and total-retry budget on top
of the per-page retry cap, so one dataset timing out can't take the
other's already-completed result down with it; a `finalize` job merges
both jobs' results (`scripts/merge_manifest.py`) before running the
insight agent and opening a PR. Full rationale and the worst-case runtime
math are in `CLAUDE.md`'s Phase 2 design section.

## Dashboard components

- Top-10 table: zip codes ranked by Class C violation percentage.
- Stacked bar chart: x-axis = zip code, y-axis = violation count, stacked by class (A/B/C).
- Line chart: trend of Class C violation counts over time for the top zip codes.

## Folder structure

- `data/static/` – NYC violations snapshot for the controlled experiment.
- `data/live/` – NYC violations / 311 data for the weekly pipeline (see Phase 2 design summary above).
- `.claude/agents/` – Claude Code subagent definitions.
- `outputs/` – dashboards, charts, and comparison tables.
- `archive/` – discarded or superseded runs kept for reference (e.g. early runs with uncontrolled variables). Not used for official results — see `lessons-learned.md` for why each one was archived.

## Status

**Phase 1: complete**, including the full MAST-taxonomy failure-mode tagging
pass. Single-agent and multi-agent pipelines both built, run once (one-shot
methodology), and scored against `rubric.md` by both a human reviewer and an
isolated AI self-score session. See Results summary above, `results.md` for
full detail (including the MAST tagging section), and `lessons-learned.md`
for the methodology decisions and failure modes discovered along the way (17
logged lessons, spanning data-schema scoping, model pinning, skill-invocation
risks, and the specific spec-adherence failure behind multi-agent's lower
score).

**Phase 2: live and running on a schedule.** `scripts/socrata_pipeline.py` and
`scripts/refresh_weekly.py` implement the locked design (datasets, rolling
12-month window, manifest-based handoff), plus a storage redesign found by
actually trying to push the first production bootstrap: canonical files
are local working state only, never committed (see "Phase 2 design summary"
above), and both datasets now do a full re-fetch every run rather than an
incremental split-query. The insight agent (`.claude/agents/insight-agent.md`)
reads the manifest and baseline and writes `data/live/latest_insight.md`;
`scripts/insight_signals.py` precomputes its anomaly arithmetic
deterministically rather than leaving that to the agent — verified offline
across a simulated two-run sequence — see `CLAUDE.md`'s Phase 2 design
section for full detail. The GitHub Actions workflow
(`.github/workflows/weekly-refresh.yml`) is now built. A dry run (short
`window_days`, `dry_run: true`) confirmed the three-job split, the
artifact handoff between jobs, the baseline-change guard, and the
insight agent's headless invocation all work end-to-end — see
`CLAUDE.md`'s "Where to start" section for that run's details (including
an artifact-path bug found and fixed along the way). **The first real,
full-window production run succeeded on 2026-10-05** (~54 minutes,
reviewed and merged) — the weekly cron is now live.

**Phase 3: not yet started.** The `data-cleaner` spec-adherence failure from
Phase 1, and the Inter-Agent Misalignment gap identified in the MAST pass
(a downstream agent's correct diagnosis never routed back to fix the
upstream deliverable), are both natural, concrete test cases for the Phase 3
audit skill once built.
