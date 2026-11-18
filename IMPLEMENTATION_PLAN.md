# Implementation Plan

1. **Foundation** — `db.py` schema/migrations, `models.py` shared evidence schema, `tokens.py`.
2. **Extraction** — extractors per family + registry; `scanner.py`; unit tests on fixtures + real repos.
3. **Agreement index** — `agreements.py` scoring + holder queries.
4. **Diff analysis** — `diffs.py` parser, removed/rename/value-change, candidates with dual locations.
5. **Replay + baseline** — `replay.py`: cutoff index via `git worktree`-free `git archive` snapshot, co-change baseline, metrics.
6. **Trajectories** — adapters → `NormalizedEvent`; classification; path mapping (repo-relative, commit-aware); ingest.
7. **Navigation** — first edit, post-edit navigation, detours, edges, baseline, lift, score; gold-patch eval.
8. **Ranker** — feature assembly, weighted fusion, LR training from replay labels, confidence + explanations.
9. **Interfaces** — CLI, FastAPI + static UI, Claude Code Stop hook (+ `.claude/settings.json` example).
10. **Verification** — pytest suite; end-to-end run on the cloned real repos and real trajectories; report in `README.md`.

Dependency order: 1 → 2 → 3 → 4 → 5; 1 → 6 → 7; (4,7) → 8 → 9 → 10.
