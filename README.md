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
   - A deterministic script pulls new records and recomputes metrics weekly.
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
upsert-by-ID into a canonical current file, plus immutable dated history
snapshots — not append-only — specifically to avoid the duplicate-row
corruption a naive append design would cause on a mutable feed.

**Rolling 12-month window**, computed dynamically each run, replacing
Phase 1's fixed 2025-01-01 cutoff — appropriate for a one-time static
comparison, wrong for an ongoing live pipeline where a fixed cutoff would
let the "current" file grow unbounded and dilute anomaly detection with
stale cases. Full history beyond 12 months lives in the dated snapshots.

**Handoff:** the refresh script writes `weekly_manifest.json` with full new/
updated rows embedded (not just IDs), so the insight agent reads one small
file instead of re-scanning the full canonical dataset. The agent only runs
if a manifest exists for that run, which doubles as the enforcement
mechanism for the pipeline's fail-fast rule (no partial writes on error).

**Pull strategy differs by dataset, deliberately.** Testing against the live
API found a full 365-day re-fetch of the 311 dataset (28M+ rows citywide)
costs ~3 hours/week regardless of page size — the `WHERE` filter itself is
the fixed cost, not pagination. 311 now runs two smaller queries per week
("new since last success" + "still-open status recheck") instead, cutting
that to ~10-15 minutes; HPD's smaller table stays a single full-window query.
Full numbers, the accepted risk this trades for, and a rejected `:updated_at`
approach are in `CLAUDE.md`'s Phase 2 design section.

**Infra:** GitHub Actions cron (public repo, free, uncapped), manual
`workflow_dispatch` also enabled for testing, NYC Open Data app token stored
as a GitHub Actions secret (never committed).

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

**Phase 2: refresh script implemented and validated against the live API,
not yet deployed.** `scripts/socrata_pipeline.py` and `scripts/refresh_weekly.py`
implement the locked design (datasets, upsert + dated history snapshots,
rolling 12-month window, manifest-based handoff), plus a pull-strategy fix
found by actually running the script against live Socrata data — see the
Phase 2 design summary above and `CLAUDE.md` for full detail. Not yet done:
the GitHub Actions workflow wiring the script to a weekly cron, the first
real production backfill into `data/live/`, and the insight agent itself.

**Phase 3: not yet started.** The `data-cleaner` spec-adherence failure from
Phase 1, and the Inter-Agent Misalignment gap identified in the MAST pass
(a downstream agent's correct diagnosis never routed back to fix the
upstream deliverable), are both natural, concrete test cases for the Phase 3
audit skill once built.
