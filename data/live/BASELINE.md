# Provenance: `data/live/baseline_summary.json`

This file is the **permanent, never-overwritten** reference point each live
dataset's anomaly signals are compared against (see `CLAUDE.md`'s "Bootstrap
baseline" section). It cannot be regenerated — the live NYC Open Data feeds
have moved on since these runs, so there is no way to recreate the exact
numbers below from scratch. This note exists purely to record where it came
from, after a 2026-10-05 git-history cleanup (see "History note" below)
disconnected the file's commit lineage from its real creation dates.

## Per-dataset provenance

| Dataset | `generated_at` | Rows (`total_count`) | Window covered | Captured in (original commit) |
|---|---|---|---|---|
| `hpd` | 2026-09-11 | 886,413 | 2025-09-11 – 2026-09-11 (rolling 365-day window as of capture) | `eed2cc18f63e9b70e11131f9b81e57577ff0e3e7` |
| `311` | 2026-09-16 | 893,516 | 2025-09-16 – 2026-09-16 (rolling 365-day window as of capture) | `0c8d28680f125c14c02a873e088c1739fc7ddd14` |

Both entries were captured by `scripts/socrata_pipeline.py`'s
`write_baseline_entry_if_missing` on each dataset's first-ever successful
live bootstrap run, per the original Phase 2 implementation (before the
2026-10-05 full-re-fetch/no-committed-CSV redesign in `CLAUDE.md`).

## Integrity

**SHA-256 of `data/live/baseline_summary.json`** (as committed in this same
commit — recompute and compare if this file is ever touched):

```
30d255c1c292d3effa66896c1d5c3a06f1a1374481aaa9e043bc4f74266b3dd2
```

Verified byte-identical to the content originally committed in
`0c8d28680f125c14c02a873e088c1739fc7ddd14` (`git diff 0c8d286 HEAD --
data/live/baseline_summary.json` produces no output) — confirmed
2026-10-05, before that commit's lineage was disconnected from `main` (see
below).

Also protected going forward by an automated guard: the `finalize` job in
`.github/workflows/weekly-refresh.yml` fails the run if
`git diff --exit-code data/live/baseline_summary.json` shows *any* change
after `scripts/merge_manifest.py` runs — this file is not expected to
change again now that both configured datasets already have an entry, so
any diff (including from a short-window dry run) is treated as a bug, not
a legitimate update.

## History note

On 2026-10-05, fixing an unrelated problem (the original bootstrap commits
included canonical CSVs too large for GitHub's 100MiB per-file push limit,
and had never been pushed) was done via `git reset --soft` + recommit
rather than a history-preserving rewrite. That correctly dropped the
oversized CSVs, but also disconnected this file's real commit history —
`git log --follow data/live/baseline_summary.json` on `main` now only
shows the 2026-10-05 replacement commit, not the original
`eed2cc1`/`0c8d286` commits above. Those two commits still exist and are
not garbage-collected: a local-only branch,
`backup/pre-reset-phase2-bootstrap`, points at `0c8d286` specifically to
keep them reachable. **That branch is local-only and must never be
pushed** — it exists only so these objects survive `git gc`, not as a
public record (it would reintroduce the oversized CSVs if pushed). This
file is the durable, committed substitute for that lost lineage.
