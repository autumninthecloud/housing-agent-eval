# Results — housing-agent-eval Phase 1

Run-by-run log of cost, latency, and rubric scores for the single-agent vs.
multi-agent comparison. See `rubric.md` for scoring criteria and
`lessons-learned.md` for the reasoning behind each methodology decision
referenced below.

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

### Run: Single-agent, Phase 1, pinned (official baseline)

*(Not yet run. Protocol: pin model via `claude --model claude-sonnet-5`, verify
with `/model` only — do not invoke or inspect any skill mid-session. Commit
`outputs/single_agent/` and `scripts/pipeline.py` to git immediately
after capturing `/cost`, before doing anything else in that session.)*

---

### Run: Multi-agent, Phase 1, pinned

*(Not yet run — placeholder for when the multi-agent pipeline is built.)*

---

## Cross-architecture comparison

*(Fill in once both architectures have a completed, scored run.)*

| Metric | Single-agent | Multi-agent |
|---|---|---|
| Cost | $0.75 | ___ |
| Latency (API) | 3m 27s | ___ |
| Spec-match (human) | ___ | ___ |
| Spec-match (AI self-score) | ___ | ___ |
| Failure modes (MAST-tagged) | ___ | ___ |
