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
  - See "Phase 2 design (implemented)" below for the full concrete spec.

- Phase 3 (governance audit):
  - Create a governance-audit skill that scores agent setups against NIST AI RMF agentic gaps (autonomy tier, tool scoping, delegation logging, override points).
  - Wire this into a weekly GitHub Action.

## Data locations

- `data/static/` – NYC Housing Maintenance Code Violations, filtered snapshot since 2025-01-01 (use NOVIssuedDate, not InspectionDate). Trimmed to 5 columns: ViolationID, Borough, Postcode, Class, NOVIssuedDate. This schema is fixed for Phase 1 only — do not add or remove columns once the single-agent/multi-agent comparison begins, since column count affects the cost/latency metrics being compared.
- `data/live/` – NYC HPD violations + 311 complaints (full rolling-window re-fetch every run — see "Pull strategy" below for why this replaced an earlier incremental design). Not subject to the Phase 1 column restriction. See "Phase 2 design (implemented)" below for the exact schema, storage layout, and rationale.

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

## Phase 2 design (implemented)

This section originally recorded the finalized Phase 2 design, agreed
before any code was written, so implementation could be checked against
it rather than improvised mid-build. It has since been updated in place
multiple times as real implementation and operation (live API behavior,
GitHub's push-size limit, three pre-launch review passes) revised parts
of the original plan — those revisions are documented inline below, not
hidden; this heading just no longer claims the design is pre-implementation.

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
Note this window only bounds what counts as "current" in the canonical
files — it doesn't preserve older records anywhere else; see Storage design
below for why a separate historical archive was deliberately not built.

- HPD: `NOVIssueDate ≥ today − 365d`
- 311: `created_date ≥ today − 365d`, `agency = 'HPD'`

### Pull strategy: full re-fetch every run, for both datasets

**Current design: both HPD and 311 do a full rolling-window re-fetch every
run.** This reverses an earlier 311-only incremental "split query"
optimization (history below) — reversed not because the optimization
didn't work (it did, and was measured and tested), but because of what it
required: an incremental upsert against *last run's full canonical file*,
which in turn required that file to persist between runs. It turned out
that file couldn't be committed to git at all (see Storage design below —
GitHub rejects pushes of files over 100MiB, and 311's canonical file is
~124MB), and a persistence mechanism *outside* git (cache, release asset,
external store) was judged not worth the complexity for a job that can
simply afford to run longer instead. ~3 hours/week of runtime on a free,
uncapped, nobody's-waiting-on-it scheduled job was accepted as the
simpler tradeoff over introducing new infrastructure just to keep an
optimization alive.

**What was tried and measured, against the live Socrata API** (kept here
as a record of real numbers, even though the split-query design built on
top of them was reversed):

- 311 (`erm2-nwe9`) is a 28M+-row citywide table. A single filtered,
  paginated page (`created_date` + `agency='HPD'`, `$order` by either
  `unique_key` or the internal `:id`) consistently took **267-350 seconds**,
  regardless of `$limit` (5,000 vs. 50,000 made no measurable difference —
  325s vs. 267-350s) or which column it was ordered by (`:id` was actually
  slightly slower, at 349s, than `unique_key`). This means the cost is a
  fixed scan/filter cost paid once per query, not a pagination or sort cost —
  a `count(*)` query with the same `$where` returned in 5.6s, confirming that
  materializing and paging through full rows (not filtering/counting) is
  what's expensive on this table.
- HPD (`wvxf-dwi5`) is a much smaller underlying table. A filtered page took
  33s at `$limit=5000` and 66.5s at `$limit=50000` — real cost, but far
  below 311's, and it does scale somewhat with page size (unlike 311's flat
  cost), consistent with a smaller base table.
- Consequence: a full 365-day re-fetch of 311 needs ~33 pages even at the
  largest practical page size, at ~300-350s/page → **~3 hours/week**. The
  same full-re-fetch approach for HPD, at `page_size=50000`, needs only ~36
  pages at ~66.5s/page → **~40 minutes/week**.

**History — the split-query design that was built, tested, and then
reversed:** 311 originally ran two queries per run instead of one
full-window query — *(1) new since last successful run* and *(2) still-open
rows needing a status re-check* (closed complaints are effectively
immutable, so skipping re-fetch of closed-and-unchanged rows is where the
time savings came from) — cutting 311's weekly runtime from ~3 hours to
~10-15 minutes. It worked and was verified against the live API. It was
reversed once the git push-size problem (Storage design below) was
discovered on the first attempt to actually push the production bootstrap:
an incremental upsert strategy is only correct if last run's full canonical
file is available to merge into, and there was no durable place to keep
that file that didn't add real new infrastructure. Accepting the longer
runtime was simpler than solving that storage problem just to keep the
optimization.

**Rejected alternative — `:updated_at` filtering**: before landing on the
new/still-open split (back when that design was still in use), filtering
311 by Socrata's internal `:updated_at` system column
(`:updated_at >= last_successful_run`) was tested as a way to find only
genuinely-changed rows. It was rejected: counts of rows with `:updated_at`
in the last 1 day (451,960), 7 days (468,474), and 60 days (559,861) were
all roughly the same size despite the wildly different window lengths — the
signature of a bulk reindex/republish event touching hundreds of thousands
of rows at once, not per-row edit tracking. `:updated_at` is not a reliable
"this row's content actually changed" signal on this dataset. Documented
here so this dead end isn't re-discovered and re-tested later.

### Storage design: canonical files are local working state, never committed

Because both datasets are mutable (existing records get status updates, not
just new records appended), naive append-only storage would create duplicate
rows for the same entity every time its status changes — silently corrupting
any count-based analysis. Storage is a single **canonical current file** per
dataset, one row per entity ID, **upserted** each run (new IDs added,
existing IDs overwritten if the record's content is newer).

- `data/live/hpd_violations_current.csv`
- `data/live/311_complaints_current.csv`

**These files are not committed to git**, and are not meant to be read by
anything outside the run that produced them (not even the insight agent —
see Insight agent below). This was not the original design — see below —
but it's load-bearing now: `.gitignore` excludes `data/live/*.csv`, and the
GitHub Actions workflow treats them as disposable local output of each run,
never carried forward.

**Why this changed:** the original design committed the canonical CSVs to
the repo every run, upserted in place, specifically to avoid the unbounded
growth of a dated history archive (see below). That worked until the first
real attempt to push the production bootstrap failed: GitHub rejects any
pushed file over 100MiB, and 311's canonical file alone is ~124MB (HPD's,
at ~92MB, was already closing in on the limit too, and would have crossed
it as the rolling window kept collecting rows). Git LFS was considered and
rejected — LFS stores each version of a tracked file as an independent
blob with no delta compression against the previous version, so a file
that gets fully rewritten every run would add a full ~100-125MB to LFS
storage *every single week*, forever — the same unbounded-growth problem
the history archive below was already rejected for, just moved one layer
down, and on a much smaller free quota (1GB storage/bandwidth) than git
itself has. Persisting the file outside git entirely (a GitHub Release
asset, external blob storage) was also considered, but every one of those
options exists only to keep alive an optimization (311's incremental
split-query fetch, see Pull strategy above) that itself only exists to
avoid a few hours of runtime on a free, uncapped, nobody's-waiting job.
Dropping that optimization — full re-fetch every run, for both datasets —
removed the need for persisted state entirely: nothing has to survive
between runs for the output to be correct, so there's nothing to solve a
storage problem for.

**No dated history snapshots are written either.** An earlier version of
this design called for an immutable per-run snapshot archive
(`data/live/history/{dataset}_YYYY-MM-DD.csv`) for reproducibility. That was
dropped after sizing it against the real data volume: at measured row counts
(~1.6-1.8M rows/dataset in the trailing-year window), each dataset's snapshot
alone runs ~180-190MB, and since a history archive is by definition never
pruned, committing it would add that much to the repo *every single run*,
indefinitely. The same unbounded-growth reasoning that killed this design is
exactly what later killed committing even a single current-state file, and
then what killed Git LFS as a workaround for that — see above.

**What actually gets committed each run**, and stays small regardless of
how large the live datasets grow: `weekly_manifest.json`,
`baseline_summary.json`, and the insight agent's `latest_insight.md`. None
of these ever embed raw rows — see Bootstrap baseline and Handoff below.

Per `README.md`, Phase 2's live schema is not subject to Phase 1's 5-column
restriction — column sets below were chosen for what the refresh script
and insight agent need (anomaly flagging, narrative, potential mapping),
not parity with Phase 1's static file. These are the *local, uncommitted*
canonical files' columns — not part of the repo's committed state.

**HPD canonical schema:** `ViolationID, BoroID, Zip, Latitude,
Longitude, Class, NOVIssueDate, CurrentStatus, CurrentStatusDate`

**311 canonical schema:** `unique_key, agency, complaint_type,
descriptor, borough, incident_zip, latitude, longitude, created_date,
closed_date, status`

### Bootstrap baseline: `data/live/baseline_summary.json`

`weekly_manifest.json` never embeds raw rows, for any run — not just a
dataset's first run (see Handoff below). That sidesteps the manifest-size
problem a raw-row approach would otherwise have: measured directly on this
project's own data, embedding all rows from a dataset's first-ever full
window would cost ~1.26GB combined for both datasets (~389 bytes/row in
JSON, measured from a smaller live test: 3,474,421 bytes for 8,934 rows) —
comparable in size to the entire dataset. Since the manifest only ever
carries counts and aggregate stats, this cost never materializes regardless
of how a given run's numbers look.

What a dataset actually needs captured once, though, is a **fixed
reference point** to compare every future run against — without one, a
run's own stats have nothing to be "notable" relative to. On a dataset's
first-ever successful run, `write_baseline_entry_if_missing` computes and
commits a small set of **aggregate** stats (not raw rows) to
`data/live/baseline_summary.json`, once per dataset, as a **permanent,
never-overwritten** reference point — written once when a dataset first
has data, then left alone forever, unlike the manifest (regenerated every
run) and the canonical files (local, uncommitted, regenerated every run
per Storage design above).

**What's in it, per dataset:** `total_count`; a `by_{field}` breakdown
(count + percentage, top 15 values) for each of
`DatasetConfig.baseline_categorical_fields` (HPD: `class`, `currentstatus`;
311: `status`, `complaint_type`); `top_zips_by_count` (top 15, if
`baseline_zip_field` is set — HPD: `zip`, 311: `incident_zip`); and, only
for HPD, `top_zips_by_target_concentration` — top zips by Class C
percentage, deliberately mirroring Phase 1's own ranking methodology
(zips under 5 total rows are excluded to avoid noisy 100%-style
concentrations from a near-empty sample). Verified offline (mocked fetch,
no live API calls) against synthetic data: bootstrap detection, row
omission, accurate counts despite omitted rows, correct aggregate math
including the concentration ranking, and the write-once guarantee (a
second run for the same dataset leaves the file's contents/mtime
unchanged) all confirmed.

**Why this file matters beyond solving a size problem:** it's also the
fixed reference point the insight agent needs to say anything about
*change over time* — see Insight agent below. Without it, every run's
narrative could only describe that run's own totals in isolation, with no
"compared to what" to anchor against.

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
  partway through, that dataset's canonical file is left completely
  untouched for this run (no half-written state), and the manifest records
  that dataset as failed for this run rather than silently reusing stale
  data as if it were fresh. This was a deliberate choice over
  whole-run atomicity: 311 (a 28M-row citywide feed) is more likely to have
  a flaky pull than HPD, and a whole-run failure policy would let 311's
  instability block otherwise-healthy HPD updates indefinitely. The
  atomicity guarantee that actually matters — never let a canonical file
  end up half-updated — is preserved either way; what changed is only the
  scope of what must succeed together. As of 2026-10-05 this independence
  extends to the GitHub Actions level too — see "Separate jobs per
  dataset" below.
- **Trigger:** GitHub Actions scheduled workflow (`on.schedule.cron`, weekly),
  with `workflow_dispatch` also enabled so runs can be triggered manually for
  testing without waiting a week. Repo is public, so Actions minutes are free
  and uncapped. Known platform quirk to budget for: cron schedules are
  silently disabled after 60 days of repository inactivity — worth an
  occasional manual trigger or commit if the repo goes quiet. A
  workflow-level `concurrency` group (`weekly-live-data-refresh`,
  `cancel-in-progress: false`) prevents a manual `workflow_dispatch` from
  overlapping an in-progress scheduled run against the same Socrata app
  token — two simultaneous heavy pulls would split the token's rate-limit
  ceiling and worsen 311's already-known flakiness for both runs. A
  second run queues rather than cancels the first, so a manual trigger
  never discards in-progress work.
- **In-script deadline, not just a platform-level `timeout-minutes`,
  reviewed and implemented 2026-10-05.** A GitHub Actions job-level or
  step-level `timeout-minutes` is a hard, ungraceful kill: no manifest
  gets written, no partial credit for work already done — on the old
  single-job design, a timeout mid-311-fetch would have silently thrown
  away HPD's already-successful result too, since the combined manifest
  was only written once at the very end. `socrata_pipeline.py` now takes
  an explicit `deadline` (an absolute `time.monotonic()` timestamp,
  threaded through `run_all_datasets` → `run_dataset_refresh` →
  `fetch_all_rows` → `_fetch_page`), checked **between pages and before
  every retry sleep** (not during an in-flight request, which can't be
  interrupted mid-`urlopen`). On expiry it raises `DeadlineExceededError`
  — a `DatasetRefreshError` subclass, so it's caught by the same existing
  failure-handling path and turned into a normal `"failed"` manifest
  entry, with no special-casing needed. If a dataset's deadline has
  already passed before its turn even starts (relevant in the legacy
  combined "both datasets, one deadline" local-run mode — see
  `refresh_weekly.py`), it gets a `"never started"` failed entry rather
  than being silently skipped. `timeout-minutes` still exists at the job
  level as a backstop in case this mechanism itself has a bug, not as the
  primary safety net.
- **Per-dataset total retry cap, alongside the existing per-page cap,
  same review.** `MAX_FETCH_RETRIES=5` only bounds a single page in
  isolation; nothing previously stopped a dataset under sustained
  throttling from needing a couple of retries on *every* page, costing up
  to ~63 minutes per page (see the worst-case math below) without any one
  page ever tripping its own cap. `MAX_TOTAL_RETRIES_PER_DATASET=50`
  (`_RetryBudget`, shared across every page of one dataset's
  `fetch_all_rows` call, checked at the same before-the-retry-sleep
  checkpoint as the deadline) catches that pattern and raises
  `RetryBudgetExceededError` — also a `DatasetRefreshError` subclass — well
  before it could consume the whole deadline. 50 was chosen as comfortably
  above what isolated, normal transient flakiness should cost across a
  ~33-36 page pull (a handful of 1-2-retry blips), so crossing it is a
  signal of systemic trouble, not a false alarm from an ordinary bad page.
- **Worst-case single-page failure time**, from `MAX_FETCH_RETRIES=5`,
  `RETRY_BACKOFF_BASE_SECONDS=5.0`, `REQUEST_TIMEOUT_SECONDS=600`: 6 total
  attempts (1 + 5 retries) before giving up, each able to hang up to 600s,
  plus 5+10+20+40+80=155s of backoff sleeps between them ≈ **63 minutes
  for one page to definitively fail** — this is the number both the
  in-script deadline and the retry budget above exist to interrupt well
  before it can repeat across many pages. Stacked against real page
  counts (both datasets full-re-fetch every run — see Pull strategy
  above): 311 (~33 pages, ~300-350s/page clean) failing on its last page
  costs ~32 successful pages + one ~63-min failing page ≈ **~4.1-4.5
  hours** worst case; HPD (~36 pages, ~66.5s/page clean) adds a smaller
  amount if it degrades too. A genuinely pathological case (every page on
  a dataset maxing out every retry) can still mathematically exceed
  GitHub's 360-minute hard cap for hosted runners — the in-script deadline
  doesn't prevent that, it just guarantees a clean, labeled failure well
  before GitHub's generic hard-kill would otherwise be what stops it.
- **Separate jobs per dataset (`refresh-hpd`, `refresh-311`), reviewed and
  implemented 2026-10-05.** Before this, both datasets ran sequentially
  inside one job/one script invocation, and (per the in-script-deadline
  bullet above) a job-level timeout killing that one job could lose a
  dataset's already-completed result along with the one still running.
  Splitting into separate GitHub Actions jobs means each dataset gets its
  own `timeout-minutes` backstop and its own runner, so one dataset's
  platform-level kill genuinely cannot affect the other's result. Each
  job runs `refresh_weekly.py --dataset {hpd,311} --deadline-minutes N
  --output data/live/partial_manifest_{name}.json` (120min for HPD,
  270min for 311 — sized to each dataset's own expected workload, not a
  single number covering both) and uploads its partial manifest plus its
  local `baseline_summary.json` as an artifact (`if: always()`, so a
  partial result still gets uploaded even after an in-script-deadline
  failure — though if the *job-level* timeout is what actually fires
  instead, meaning the in-script deadline somehow didn't, there's only a
  brief cancellation grace period for the upload to complete, with no
  guarantee). A third job, `finalize` (`needs: [refresh-hpd, refresh-311]`,
  `if: always()` so it still runs if one or both upstream jobs failed or
  were killed), downloads both artifacts (`continue-on-error: true` on
  each download, since a missing artifact — its job never got that far —
  must not fail finalize), and runs `scripts/merge_manifest.py` to combine
  them into the final `weekly_manifest.json`: a dataset named in
  `--expected` with no matching partial gets a synthesized `"failed"`
  entry (`"No partial manifest found for this dataset this run"`), with
  `last_successful_run` chained forward from the previously-committed
  manifest so staleness tracking doesn't silently break. `finalize` then
  runs the insight agent (if ≥1 dataset succeeded) and opens the PR, same
  as before.
- **Pre-launch review additions, 2026-10-05** (same day as the job split
  above, caught in a second review pass before the first real run):
  - `finalize`'s `if:` is `${{ !cancelled() }}`, not `always()` — must
    still run after a refresh job's ordinary failure or timeout (that's
    the whole point of the job split), but must NOT barge ahead and open
    a PR if a human explicitly cancels the workflow run.
  - `workflow_dispatch` gained two inputs: `dry_run` (boolean — skips only
    the final "Open PR" step; fetch, merge, and the insight agent all
    still run, so a dry run genuinely exercises the artifact handoff
    between jobs and the headless agent call) and `window_days` (string
    override for `refresh_weekly.py --window-days`, threaded into both
    refresh jobs — overrides a dataset's normal 365-day window to a few
    days so a dry run finishes in minutes instead of hours). **Never use
    a short window on a real run** — `total_current` and the
    baseline-relative `signals` would reflect only that narrow slice.
  - `refresh_weekly.py` logs peak resident set size (`resource.getrusage`,
    Linux-only — a no-op on Windows, fine since this only needs to work on
    the Actions runner) at the end of every invocation. Not idle curiosity:
    a real OOM kill during HPD's first bootstrap (see `upsert_rows`'s
    docstring) is exactly the failure mode worth watching for on a
    CI runner, which may be more memory-constrained than a local machine.
  - Each job's `timeout-minutes` margin above its own `--deadline-minutes`
    (30 min for both HPD and 311) already exceeded the reviewed minimum
    (deadline + ~10 min, covering one in-flight request's worst-case
    REQUEST_TIMEOUT_SECONDS=600s overrun past the deadline check) — no
    change needed there, just confirmed.

### Handoff to the insight agent: `weekly_manifest.json`

The refresh script's last step writes a manifest that the insight agent
reads instead of the full canonical files. Per the per-dataset failure model
above, the manifest reports status independently for each dataset rather
than being all-or-nothing. Current shape (never embeds raw rows, for any
run — see Bootstrap baseline above):

```json
{
  "run_date": "2026-09-06",
  "datasets": {
    "hpd": {
      "status": "success",
      "total_current": 1048713,
      "signals": {
        "basis": "this run's full aggregate stats compared against baseline_summary.json",
        "category_shifts": [
          {"field": "class", "value": "C", "this_run_pct": 38.2, "baseline_pct": 31.43, "delta_pts": 6.77}
        ],
        "new_zip_entrants": [ {"zip": "10006", "count": 94} ],
        "total_count": {"this_run": 1048713, "baseline": 886413}
      }
    },
    "311": {
      "status": "failed",
      "error": "HTTP 503 from Socrata",
      "last_successful_run": "2026-08-30"
    }
  }
}
```

A dataset with `status: "failed"` contributes nothing else to the manifest
and its canonical file is untouched this run (see Failure handling above) —
`last_successful_run` lets the insight agent (and anyone reading the
manifest) know how stale that dataset currently is.

**A `success` entry only has a `signals` key if the dataset already had a
baseline entry *before* this run.** A dataset's first-ever successful run
(or, equivalently, any run where `write_baseline_entry_if_missing` is about
to write that dataset's baseline for the first time) has nothing to compare
against yet — `total_current` is still accurate, but `signals` is simply
absent. `socrata_pipeline.run_all_datasets` reads `baseline_summary.json`
once, before any dataset in the run is processed, specifically so a
dataset getting its baseline written *this* run isn't diffed against the
baseline that was just captured from this same run's own data.

**`last_successful_run` is read from the previously-committed manifest, not
from local files.** There's no local per-run history to scan (see Storage
design above — no history/ directory, and the canonical CSVs themselves
aren't committed either). Instead, before writing this run's manifest, the
script reads whatever manifest is already sitting at
`data/live/weekly_manifest.json` from the *previous* run: if a dataset's
entry there shows `status: "success"`, that manifest's own `run_date`
becomes this dataset's `last_successful_run`; if it shows `"failed"`, its
own `last_successful_run` is carried forward unchanged (correctly chaining
through any number of consecutive failures back to the last real success,
or to `null` if it has never once succeeded). This is purely informational
now (nothing queries differently based on it — both datasets always fetch
the full window) but still valuable for the insight agent's staleness
narrative on a failed dataset. This is why the manifest has to be part of
what's committed each run — a value that only ever lived in an uncommitted
local file would vanish on GitHub Actions' next fresh checkout.

**Design rationale:** anomaly arithmetic belongs in the cheap deterministic
script, not the agent — `scripts/insight_signals.diff_against_baseline`
computes it from two small, already-aggregate stat dicts (this run's,
freshly computed; the baseline's, read from disk), never from raw rows.
Since the agent step is the more expensive, slower, and more error-prone
part of the pipeline per Phase 1's own findings, pushing that work onto the
script keeps the agent's job limited to judgment (which flagged shifts are
worth a sentence) and writing the narrative.

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
- **Reads two files, both small and bounded — not the full canonical
  files, and never any raw rows:**
  1. `weekly_manifest.json` — `status` and `total_current` per dataset,
     plus (only when a baseline already existed before this run) a
     `signals` block: this run's aggregate category/zip stats diffed
     against the baseline, already computed deterministically before the
     agent ever sees the file. There is no "delta" in the row-level sense
     — both datasets fully re-fetch their rolling window every run (see
     Pull strategy above), so there's no previous run's rows to diff
     against; `signals` compares this run's *aggregate totals* to the
     baseline's aggregate totals, not row-by-row.
  2. `data/live/baseline_summary.json` — the permanent, never-overwritten
     reference point each dataset was captured at on its first successful
     run.

  Reading only the manifest was the original design; it was extended to
  also read the baseline once it became clear a bare status/count by
  itself has no "compared to what." `weekly_manifest.json` alone lets the
  agent see this run's totals, but not whether they're notable — e.g.
  answering "is this run's Class C share higher than where this dataset
  started" requires the baseline's `by_class`/concentration figures as the
  comparison point. Both stay small and bounded regardless of how large
  the canonical files grow: the manifest by construction (aggregate stats
  only, never raw rows, for any run — see Bootstrap baseline above), the
  baseline by construction (fixed aggregate stats, written once, never
  grows).
- Responsibilities per original Phase 2 scoping: flag anomalies, generate
  short narrative insights — informed by comparing this run's aggregate
  stats against the baseline, not by inspecting individual rows.

**Implemented.** The agent definition is `.claude/agents/insight-agent.md`.
Per Phase 1's own finding that agent reasoning is the expensive,
error-prone part of the pipeline, the anomaly *arithmetic* (category-mix
deltas vs. baseline, new-zip-entrant detection) is computed
deterministically: `socrata_pipeline.run_all_datasets` computes this run's
full aggregate stats (`compute_baseline_stats`, the same function that
builds `baseline_summary.json`) and hands both that and the dataset's
existing baseline entry to `insight_signals.diff_against_baseline`, which
attaches the result as a `signals` key on the manifest entry — before the
manifest is ever written, let alone read by the agent. The agent still
reads exactly the two files described in Handoff above; it isn't the one
doing the percentage math. The agent's job is judgment (which flagged
shifts are actually worth a sentence) and writing
`data/live/latest_insight.md` (overwritten each run, no dated archive —
same rationale as the rest of this design). Thresholds live at the top of
`insight_signals.py` (`CATEGORY_DELTA_THRESHOLD_PTS`, `TOP_N_NEW_ZIP_ENTRANTS`)
if they need tuning once real weekly runs accumulate.

## Where to start

1. For Phase 1 (complete), reference work is in `data/static/` and `outputs/`; subagent definitions are in `.claude/agents/`.
2. For Phase 2, the refresh script (`scripts/socrata_pipeline.py`,
   `scripts/refresh_weekly.py`) is implemented and validated against the live
   API — see the "Pull strategy" and "Storage design" subsections above for
   what changed from the original design during implementation (both
   datasets now fully re-fetch every run; neither dataset's canonical CSV
   is committed to git — see those two subsections for why). The insight
   agent is now built (see the "Insight agent" subsection above) —
   `.claude/agents/insight-agent.md` plus the deterministic
   `scripts/insight_signals.py` signal-computation step, verified offline
   (mocked fetch, no live API calls) across two simulated runs: a no-prior-
   baseline run correctly produced no `signals` key and wrote the baseline,
   and a second run correctly computed `signals` against that fixed
   baseline without mutating it.
   The GitHub Actions workflow (`.github/workflows/weekly-refresh.yml`) is
   now built: Sunday 06:00 UTC cron + `workflow_dispatch`, a workflow-level
   `concurrency` group so a manual trigger queues behind rather than
   cancels an in-progress scheduled run, three jobs (`refresh-hpd`,
   `refresh-311` — each independently timeout-bounded and running
   `refresh_weekly.py --dataset ... --deadline-minutes ...`, see "Refresh
   script behavior" above for why they're split — then `finalize`, which
   merges their outputs via `scripts/merge_manifest.py`, runs the insight
   agent headlessly (Claude Code CLI, `CLAUDE_CODE_OAUTH_TOKEN` secret)
   only when at least one dataset succeeded, then opens a PR with whatever
   changed via `peter-evans/create-pull-request` (deliberately a PR, not a
   direct push to main, so a human reviews each week's diff — including
   the insight agent's narrative — before it lands; the PR never includes
   the canonical CSVs, only `weekly_manifest.json`, `baseline_summary.json`,
   and `latest_insight.md`). Requires two repo secrets:
   `NYC_OPEN_DATA_APP_TOKEN` (already set) and `CLAUDE_CODE_OAUTH_TOKEN`
   (not yet added — run `claude setup-token` locally, which rides on the
   user's existing Pro subscription instead of separate API-credit billing,
   and add the resulting token under Settings → Secrets and variables →
   Actions). Also requires "Allow GitHub Actions to create and approve pull
   requests" enabled under Settings → Actions → General → Workflow
   permissions, enabled and confirmed under Settings → Actions → General
   → Workflow permissions (otherwise the PR-creation step fails even
   though the refresh itself succeeded).

   **First dry-run verification, 2026-10-05.** Secrets confirmed set, then
   ran `workflow_dispatch` with `dry_run: true` and `window_days: 3` (a
   tiny window, so the whole pipeline exercises in minutes instead of
   hours). First attempt: both `refresh-hpd` and `refresh-311` almost
   certainly succeeded, but `finalize` reported both as
   `"No partial manifest found"`. Root cause: `actions/upload-artifact@v4`
   strips each upload's *least common ancestor* path before storing it —
   the HPD/311 upload steps each list two files sharing `data/live/` as
   their common parent, so the artifact actually stores them flattened
   (`partial_manifest_hpd.json`, `baseline_summary.json`), not nested
   under `data/live/` as the merge step's `--partial`/`--baseline` paths
   assumed. Fixed the paths and added a "Log downloaded artifact
   contents" step (`find` on both download dirs) so any future path
   mismatch shows up directly in the log instead of another silent
   "missing" guess. Documented here because it's exactly the kind of
   artifact-handling gotcha worth not re-discovering later.

   Second attempt, same inputs: fully green. Both datasets succeeded, the
   "Guard against unintended baseline_summary.json changes" step passed
   (no diff — confirming `write_baseline_entry_if_missing`'s no-op
   behavior held under real GitHub Actions execution, not just the
   offline tests), and the insight agent's headless invocation
   (`claude -p ... --permission-mode acceptEdits`) produced a narrative
   correctly scoped to the spec: explicit point-in-time framing (not a
   trend claim), correctly judged the small new-zip-entrant counts as
   *not* hotspots relative to baseline volumes, and correctly explained
   why a short window skews toward open/early-lifecycle statuses rather
   than treating that as an unexplained anomaly. No PR opened, confirming
   `dry_run` correctly skips it. **One thing to remember about this
   result, not a bug**: any short-`window_days` test run's narrative will
   look dramatically "off vs. baseline" purely because of the tiny
   window — that's expected, not a real finding, and future dry runs will
   produce the same kind of narrative.

   **Still not verified**: a real, full-window (`window_days` blank)
   production run — expected wall-clock is now `max(~40min HPD,
   ~165-190min 311) + finalize overhead` ≈ **~3.2-3.3 hours**, not the
   ~4 hours a sequential sum would suggest, since `refresh-hpd` and
   `refresh-311` have no `needs:` on each other and run in parallel.
   Trigger one real `workflow_dispatch` run (`dry_run: false`,
   `window_days` blank), confirm actual wall-clock against that estimate,
   and check the resulting PR before trusting the Sunday cron.

   **Resolved as of 2026-10-05** (previously logged here as unresolved):
   the two commits containing the first production bootstrap under the
   old split-query design (`eed2cc1`, `0c8d286` — including the ~124MB
   311 canonical CSV over GitHub's push limit) were never pushed and were
   replaced via `git reset --soft` + a clean recommit rather than rewritten
   in place. That correctly dropped the oversized CSVs but also
   disconnected `baseline_summary.json`'s real commit lineage from `main`
   — `git log --follow` on it now only shows the replacement commit, not
   the original 2026-09-11/2026-09-16 bootstrap dates. Content was
   verified byte-identical at the time (diffed against the still-reachable
   pre-reset commit). Rather than rewrite history again to restore the
   lineage, that provenance is now recorded directly: `data/live/BASELINE.md`
   (per-dataset capture dates, row counts, window coverage, original
   commit hashes, SHA-256) plus a **local-only** branch,
   `backup/pre-reset-phase2-bootstrap`, anchored at the original `0c8d286`
   so those objects survive `git gc` instead of eventually falling out of
   the reflog — this branch must never be pushed, since it still contains
   the oversized CSVs in its tree.
3. Log metrics and findings in markdown files at the repo root (e.g., `results.md`, `failure-analysis.md`, `governance-audit.md`).
