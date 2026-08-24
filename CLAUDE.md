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

# \## Where to start

# 

# 1\. For Phase 1, work in `data/static/` and `outputs/`.

# 2\. Define subagents in `.claude/agents/`.

# 3\. Log metrics and findings in markdown files at the repo root (e.g., `results.md`, `failure-analysis.md`, `governance-audit.md`).

