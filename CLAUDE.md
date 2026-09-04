# Claude Code Project Context – housing-agent-eval

This project compares single-agent vs multi-agent LLM architectures on a housing safety BI task, then builds a small governance-audit skill and a live weekly pipeline.

## Goals

- Phase 1 (static NYC data):
  - Build a single-agent pipeline that loads NYC Housing Maintenance Code Violations (filtered to NOVIssuedDate ≥ 2025-01-01), cleans the data, ranks zip codes by Class C violation concentration (% of total violations per zip code), and produces:
    1. A top-10 zip code table ranked by Class C percentage.
    2. A stacked bar chart of violation counts by class (A/B/C) per zip code.
    3. A trend line of Class C violation counts over time for the top zip codes.
    4. A short narrative summary of findings.
  - Build a multi-agent pipeline with an orchestrator and specialist subagents (`data-cleaner`, `analyst`, `visualizer`, `narrator`) that solves the same task.
  - Compare cost, latency, accuracy, and failure modes between the two pipelines.

- Phase 2 (live NYC data):
  - Implement a deterministic weekly refresh script for NYC HPD violations + 311 housing complaints.
  - Add one "insight agent" that only runs after the refresh to flag anomalies and generate narrative insights.
  - See "Phase 2 design (locked, pre-implementation)" below for the full concrete spec.

- Phase 3 (governance audit):
  - Create a governance-audit skill that scores agent setups against NIST AI RMF agentic gaps (autonomy tier, tool scoping, delegation logging, override points).
  - Wire this into a weekly GitHub Action.

## Data locations

- `data/static/` – NYC Housing Maintenance Code Violations, filtered snapshot since 2025-01-01 (use NOVIssuedDate, not InspectionDate). Trimmed to 5 columns: ViolationID, Borough, Postcode, Class, NOVIssuedDate. This schema is fixed for Phase 1 only — do not add or remove columns once the single-agent/multi-agent comparison begins, since column count affects the cost/latency metrics being compared.
- `data/live/` – NYC HPD violations + 311 complaints (incremental weekly pulls). Not subject to the Phase 1 column restriction. See "Phase 2 design (locked, pre-implementation)" below for the exact schema, storage layout, and rationale.

## Model configuration

For the primary Phase 1 comparison, the model is pinned to `claude-sonnet-5` for
both architectures, so architecture is the only variable:

- Single-agent: launch the session with `claude --model claude-sonnet-5`, or set
  it once via `/model` before starting the build. Do not let mid-session skill
  invocations auto-route to a different model.
- Multi-agent: every subagent definition in `.claude/agents/` must set
  `model: sonnet` explicitly in its frontmatter. Do not leave `model` unset or set
  to `inherit` — both allow auto-routing that reintroduces model choice as an
  uncontrolled variable.

A separate sub-experiment (see README.md) tests multi-agent with model routing
left open. That is intentionally a different, separately logged comparison — do
not mix its results into the primary architecture comparison.

## Known pinning exception: skills override session/subagent model pins

Model pinning (session-level `--model` flag, or a subagent's `model:` frontmatter)
does not bind skills invoked mid-task. A skill with its own `model:` field in its
frontmatter can route part of the work to a different model regardless of how the
session or subagent is pinned. Observed directly: the built-in `/dataviz` skill
routed a small slice of single-agent Phase 1 work to `claude-haiku-4-5` even with
the session pinned to `claude-sonnet-5` throughout.

Decision: do not strip skill access to force artificial purity. Skills are part of
how Claude Code actually runs by default, and eliminating them would test a
sanitized setup nobody would use in practice, which defeats the point of exploring
real Claude Code behavior. Instead: leave skills available to both single-agent
and multi-agent pipelines equally, and log any resulting model-mix in `/cost`'s
"Usage by model" breakdown as part of every run's results — do not silently
average it away. If multi-agent ends up invoking no comparable skill, note that
asymmetry explicitly in `results.md` rather than treating both runs as equivalent
by default.

This is also a live example for the Phase 3 governance-audit skill: a declared
model-pinning control (this file) with an undocumented enforcement gap (skills
aren't bound by it) is exactly the kind of tool-scoping/autonomy-tier issue the
NIST AI RMF-aligned audit is meant to surface. Treat this file's own gap as a test
case when building that skill, not just a footnote here.

## Archived runs

`archive/` holds pipeline runs that don't count as official results (e.g. unpinned
model runs, pre-schema-fix runs). Each subfolder should have its own short README
explaining why it was archived. Never build on or reference files in `archive/`
when constructing a new "official" run — always start fresh.

## Phase 1 status: complete, including full MAST-taxonomy tagging

Both architectures built, run once each (one-shot methodology), scored against
`rubric.md` by both a human reviewer and an isolated AI self-score session, and
tagged against the MAST multi-agent failure taxonomy. See `results.md` for the
full run log, scores, and the MAST-taxonomy failure-mode tagging section
(per-section tags, the causal chain behind multi-agent's propagated `02018`
artifact failure, and the cross-architecture failure-mode comparison table).
`lessons-learned.md` has the 17 logged methodology decisions.

## Phase 2 design (locked, pre-implementation)

This section records the finalized Phase 2 design, agreed before any code was
written, so implementation can be checked against it rather than improvised
mid-build.

### Scope decision: not a re-run of the Phase 1 comparison

Phase 2 does **not** re-run the single-agent vs. multi-agent comparison. The
weekly refresh script is deterministic (no LLM); the insight agent is a
single agent, not orchestrator + subagents. Phase 1's own finding —
multi-agent was more expensive, slower, and its only structural advantage
(a subagent catching another's mistake) doesn't apply to a single
lightweight anomaly/narrative agent — supports single-agent as the right
default here, not a re-litigation of Phase 1. If a live architecture
comparison is ever wanted, it should be scoped as an explicit new
sub-experiment, not folded into Phase 2's build.

### Datasets

**HPD Housing Maintenance Code Violations** — `wvxf-dwi5`
(`data.cityofnewyork.us`). Same dataset as Phase 1's static snapshot, now
pulled live. Confirmed via HPD's own data dictionary (2017 PDF, still
current per field names) and the live column set: this file is **mutable,
not append-only** — `CurrentStatus`/`CurrentStatusDate` update in place as a
violation's lifecycle progresses (issued → NOV sent → certified/dismissed/
reopened). The dataset is updated daily, including both new violations and
status changes to existing ones.

**311 Service Requests from 2020 to Present** — `erm2-nwe9`
(`data.cityofnewyork.us`). Not a separate "housing complaints" dataset —
it's the citywide 311 firehose (200+ complaint categories, 28M+ rows as of
last check), filtered down. Also mutable (`status`/`closed_date` change
after creation). Superseded 2010–2019 archive (`76ig-c548`) intentionally
excluded — Phase 2 is a live/ongoing pipeline, not a historical backfill
project.

**Housing-complaint filter (311 only):** `agency = 'HPD'`. Chosen over a
curated `complaint_type` list for simplicity and robustness — catches
everything routed to HPD without needing to maintain a category list that
could drift as NYC adds/renames complaint types.

### Rolling 12-month window (both datasets)

Both live pulls filter to a **trailing 12-month window**, computed
dynamically each run (`today − 365 days`), not a fixed date. This was a
deliberate reversal of Phase 1's fixed `NOVIssuedDate ≥ 2025-01-01` cutoff,
which was correct for a one-time static comparison but wrong for an ongoing
live pipeline: a fixed cutoff would let `data/live/` grow unbounded and
dilute anomaly/trend detection with increasingly stale, mostly-closed cases.
Full historical fidelity beyond the 12-month window is preserved via the
dated history snapshots (below), so the rolling window costs nothing in
terms of reproducibility — it only bounds what counts as "current."

- HPD: `NOVIssueDate ≥ today − 365d`
- 311: `created_date ≥ today − 365d`, `agency = 'HPD'`

### Storage design: upsert current + immutable dated history

Because both datasets are mutable (existing records get status updates, not
just new records appended), naive append-only storage would create duplicate
rows for the same entity every time its status changes — silently corrupting
any count-based analysis. Two files per dataset instead:

1. **Canonical current file** — one row per entity ID, **upserted** each run
   (new IDs added, existing IDs overwritten if the record's status/date is
   newer). This is the analysis-ready file the insight agent and any
   dashboarding reads from.
   - `data/live/hpd_violations_current.csv`
   - `data/live/311_complaints_current.csv`

2. **Dated history snapshot** — a full, trimmed-column snapshot written
   once per run, under its own date, **never modified after write**. This is
   what preserves reproducibility (anyone can rebuild the exact state of the
   data as of any given run) without the canonical file growing unbounded.
   - `data/live/history/hpd_YYYY-MM-DD.csv`
   - `data/live/history/311_YYYY-MM-DD.csv`

Per `README.md`, Phase 2's live schema is not subject to Phase 1's 5-column
restriction — column sets below were chosen for what the insight agent
needs (anomaly flagging, narrative, potential mapping), not parity with
Phase 1's static file.

**HPD canonical/history schema:** `ViolationID, BoroID, Zip, Latitude,
Longitude, Class, NOVIssueDate, CurrentStatus, CurrentStatusDate`

**311 canonical/history schema:** `unique_key, agency, complaint_type,
descriptor, borough, incident_zip, latitude, longitude, created_date,
closed_date, status`

### Refresh script behavior

- **Deterministic, no LLM** — this is a data pull/upsert job, not a
  reasoning task. Explicitly specified as "deterministic" in the original
  Phase 2 scoping; this rules out any agent involvement in the refresh step
  itself, regardless of architecture.
- **Auth:** NYC Open Data / Socrata app token, stored as a GitHub Actions
  repository secret (`NYC_OPEN_DATA_APP_TOKEN`), read from the environment.
  Never committed to the repo, never printed in logs. The token is
  functionally an API key (static, identifies the calling app, raises the
  shared rate-limit ceiling) despite Socrata's "token" naming — it does not
  grant access beyond what's already public.
- **Failure handling — independent per dataset, atomic within each dataset:**
  HPD and 311 are pulled and upserted independently; one dataset's API
  failure does not block or affect the other. Within a single dataset,
  "no partial writes" still holds strictly — if a dataset's pull fails
  partway through, that dataset's canonical file and history snapshot are
  left completely untouched for this run (no half-written state), and the
  manifest records that dataset as failed for this run rather than silently
  reusing stale data as if it were fresh. This was a deliberate choice over
  whole-run atomicity: 311 (a 28M-row citywide feed) is more likely to have
  a flaky pull than HPD, and a whole-run failure policy would let 311's
  instability block otherwise-healthy HPD updates indefinitely. The
  atomicity guarantee that actually matters — never let a canonical file
  end up half-updated — is preserved either way; what changed is only the
  scope of what must succeed together.
- **Trigger:** GitHub Actions scheduled workflow (`on.schedule.cron`, weekly),
  with `workflow_dispatch` also enabled so runs can be triggered manually for
  testing without waiting a week. Repo is public, so Actions minutes are free
  and uncapped. Known platform quirk to budget for: cron schedules are
  silently disabled after 60 days of repository inactivity — worth an
  occasional manual trigger or commit if the repo goes quiet.

### Handoff to the insight agent: `weekly_manifest.json`

The refresh script's last step writes a manifest that the insight agent
reads instead of the full canonical files. Per the per-dataset failure model
above, the manifest reports status independently for each dataset rather
than being all-or-nothing:

```json
{
  "run_date": "2026-09-06",
  "datasets": {
    "hpd": {
      "status": "success",
      "new_count": 142,
      "updated_count": 38,
      "total_current": 1048713,
      "new_violations": [ { ...full row... } ],
      "updated_violations": [ { ...full row... } ]
    },
    "311": {
      "status": "failed",
      "error": "HTTP 503 from Socrata",
      "last_successful_run": "2026-08-30"
    }
  }
}
```

A dataset with `status: "failed"` contributes no rows to the manifest and
its canonical file/history snapshot are untouched this run (see Failure
handling above) — `last_successful_run` lets the insight agent (and anyone
reading the manifest) know how stale that dataset currently is.

**Design rationale:** the script already computes the new/updated ID sets
in memory while performing the upsert, and already has the full row data at
that point — so embedding full rows (not just IDs) costs the script
approximately nothing extra, but saves the insight agent a redundant lookup
against a large canonical file every single run. Since the agent step is the
more expensive, slower, and more error-prone part of the pipeline per
Phase 1's own findings, work is deliberately pushed onto the cheap
deterministic script rather than the costly agent step.

**Insight agent trigger condition:** the agent should run whenever
`weekly_manifest.json` exists for this run **and** at least one dataset
within it has `status: "success"` — it does not require every dataset to
have succeeded. The agent reasons only over datasets marked successful, and
should note in its narrative when a dataset is missing/stale this week
(e.g. "311 data unavailable this run, last updated 2026-08-30") rather than
treating a partial pipeline outage as if nothing happened. The manifest is
still only written after the refresh script's per-dataset work completes —
a run where every dataset failed produces a manifest with no successful
datasets, and the agent should skip running narrative/anomaly generation
entirely in that case (nothing to analyze).

### Insight agent

- **Single agent** (see Scope decision above) — not orchestrator + subagents.
- Runs whenever a manifest exists with at least one successful dataset (see
  Handoff section above for the exact trigger condition and partial-failure
  handling).
- Reads `weekly_manifest.json` only, not the full canonical files — keeps
  the agent's input small and bounded regardless of how large the canonical
  files grow over time.
- Responsibilities per original Phase 2 scoping: flag anomalies, generate
  short narrative insights. Specific anomaly-detection logic and narrative
  format to be defined at implementation time — not yet specified here.

## Where to start

1. For Phase 1 (complete), reference work is in `data/static/` and `outputs/`; subagent definitions are in `.claude/agents/`.
2. For Phase 2, work is not yet started — see "Phase 2 design (locked, pre-implementation)" above for the full spec before writing the refresh script.
3. Log metrics and findings in markdown files at the repo root (e.g., `results.md`, `failure-analysis.md`, `governance-audit.md`).
