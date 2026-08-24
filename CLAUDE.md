# \# Claude Code Project Context – housing-agent-eval

# 

# This project compares single-agent vs multi-agent LLM architectures on a housing safety BI task, then builds a small governance-audit skill and a live weekly pipeline.

# 

# \## Goals

# 

# \- Phase 1 (static NYC data):

# &#x20; - Build a single-agent pipeline that loads NYC Housing Maintenance Code Violations (filtered to NOVIssuedDate ≥ 2025-01-01), cleans the data, ranks zip codes by Class C violation concentration (% of total violations per zip code), and produces:

# &#x20;   1. A top-10 zip code table ranked by Class C percentage.

# &#x20;   2. A stacked bar chart of violation counts by class (A/B/C) per zip code.

# &#x20;   3. A trend line of Class C violation counts over time for the top zip codes.

# &#x20;   4. A short narrative summary of findings.

# &#x20; - Build a multi-agent pipeline with an orchestrator and specialist subagents (`data-cleaner`, `analyst`, `visualizer`, `narrator`) that solves the same task.

# &#x20; - Compare cost, latency, accuracy, and failure modes between the two pipelines.

# 

# \- Phase 2 (live NYC data):

# &#x20; - Implement a deterministic weekly refresh script for NYC HPD violations + 311 housing complaints.

# &#x20; - Add one "insight agent" that only runs after the refresh to flag anomalies and generate narrative insights.

# 

# \- Phase 3 (governance audit):

# &#x20; - Create a governance-audit skill that scores agent setups against NIST AI RMF agentic gaps (autonomy tier, tool scoping, delegation logging, override points).

# &#x20; - Wire this into a weekly GitHub Action.

# 

# \## Data locations

# 

# \- `data/static/` – NYC Housing Maintenance Code Violations, filtered snapshot since 2025-01-01 (use NOVIssuedDate, not InspectionDate). Trimmed to 5 columns: ViolationID, Borough, Postcode, Class, NOVIssuedDate. This schema is fixed for Phase 1 only — do not add or remove columns once the single-agent/multi-agent comparison begins, since column count affects the cost/latency metrics being compared.

# \- `data/live/` – NYC HPD violations + 311 complaints (incremental weekly pulls). Not subject to the Phase 1 column restriction — Phase 2's insight agent may need additional fields (e.g. status, location) for anomaly flagging and narrative generation.

# 

# \## Model configuration

# 

# For the primary Phase 1 comparison, the model is pinned to `claude-sonnet-5` for

# both architectures, so architecture is the only variable:

# 

# \- Single-agent: launch the session with `claude --model claude-sonnet-5`, or set

#   it once via `/model` before starting the build. Do not let mid-session skill

#   invocations auto-route to a different model.

# \- Multi-agent: every subagent definition in `.claude/agents/` must set

#   `model: sonnet` explicitly in its frontmatter. Do not leave `model` unset or set

#   to `inherit` — both allow auto-routing that reintroduces model choice as an

#   uncontrolled variable.

# 

# A separate sub-experiment (see README.md) tests multi-agent with model routing

# left open. That is intentionally a different, separately logged comparison — do

# not mix its results into the primary architecture comparison.

# 

# \## Known pinning exception: skills override session/subagent model pins

# 

# Model pinning (session-level `--model` flag, or a subagent's `model:` frontmatter)

# does not bind skills invoked mid-task. A skill with its own `model:` field in its

# frontmatter can route part of the work to a different model regardless of how the

# session or subagent is pinned. Observed directly: the built-in `/dataviz` skill

# routed a small slice of single-agent Phase 1 work to `claude-haiku-4-5` even with

# the session pinned to `claude-sonnet-5` throughout.

# 

# Decision: do not strip skill access to force artificial purity. Skills are part of

# how Claude Code actually runs by default, and eliminating them would test a

# sanitized setup nobody would use in practice, which defeats the point of exploring

# real Claude Code behavior. Instead: leave skills available to both single-agent

# and multi-agent pipelines equally, and log any resulting model-mix in `/cost`'s

# "Usage by model" breakdown as part of every run's results — do not silently

# average it away. If multi-agent ends up invoking no comparable skill, note that

# asymmetry explicitly in `results.md` rather than treating both runs as equivalent

# by default.

# 

# This is also a live example for the Phase 3 governance-audit skill: a declared

# model-pinning control (this file) with an undocumented enforcement gap (skills

# aren't bound by it) is exactly the kind of tool-scoping/autonomy-tier issue the

# NIST AI RMF-aligned audit is meant to surface. Treat this file's own gap as a test

# case when building that skill, not just a footnote here.

# 

# \## Archived runs

# 

# `archive/` holds pipeline runs that don't count as official results (e.g. unpinned

# model runs, pre-schema-fix runs). Each subfolder should have its own short README

# explaining why it was archived. Never build on or reference files in `archive/`

# when constructing a new "official" run — always start fresh.

# 

# \## Where to start

# 

# 1\. For Phase 1, work in `data/static/` and `outputs/`.

# 2\. Define subagents in `.claude/agents/`.

# 3\. Log metrics and findings in markdown files at the repo root (e.g., `results.md`, `failure-analysis.md`, `governance-audit.md`).

