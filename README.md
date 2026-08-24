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

- - **Static dataset (Phase 1):** NYC Housing Maintenance Code Violations, filtered to NOVIssuedDate ≥ 2025-01-01 (CSV export, stored under `data/static/`). Columns retained: `ViolationID`, `Borough`, `Postcode`, `Class`, `NOVIssuedDate`. All other source columns (`NOVDescription`, `CurrentStatus`, `CurrentStatusDate`, `ViolationStatus`, `RentImpairing`, `Latitude`, `Longitude`, `NTA`, `NOVID`) were dropped to reduce file size; none are used by the ranking, chart, or trend calculations defined above. This trimmed schema applies only to the Phase 1 static file and must stay fixed for the duration of the single-agent vs. multi-agent comparison — do not modify columns mid-experiment.
- **Live datasets (Phase 2):**
  - NYC HPD Housing Violations (NYC Open Data API, incremental weekly pulls).
  - NYC 311 Housing Complaints (NYC Open Data API).
-  Column set is not restricted to the Phase 1 schema — retain whatever fields the insight agent needs for anomaly detection and narrative context (e.g. `ViolationStatus`, `Latitude`/`Longitude`).

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

## Dashboard components

- Top-10 table: zip codes ranked by Class C violation percentage.
- Stacked bar chart: x-axis = zip code, y-axis = violation count, stacked by class (A/B/C).
- Line chart: trend of Class C violation counts over time for the top zip codes.

## Folder structure

- `data/static/` – NYC violations snapshot for the controlled experiment.
- `data/live/` – NYC violations / 311 data for the weekly pipeline.
- `.claude/agents/` – Claude Code subagent definitions.
- `outputs/` – dashboards, charts, and comparison tables.
- `archive/` – discarded or superseded runs kept for reference (e.g. early runs with uncontrolled variables). Not used for official results — see `lessons-learned.md` for why each one was archived.

## Status

Day 1: CLI installed, repo initialized, folder structure created, dataset selected and re-filtered on NOVIssuedDate.
Next step: build the single-agent pipeline in Claude Code (Phase 1, Day 2).
