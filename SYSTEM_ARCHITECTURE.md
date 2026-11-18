# SpecWeft — System Architecture

```
            repos ─▶ scanner ─▶ extractors/* ─▶ tokens (normalize, version, template) ─▶ occurrences (SQLite)
                                                                                         │
                                                       scoring (rarity/spread/specificity) ─▶ agreement index
                                                                                         │
  diff (git/unified) ─▶ diff analysis (removed / rename / value-change) ─▶ holders ─▶ agreement candidates ─┐
                                                                                                            │
  trajectories ─▶ adapters (claude_code | swe_agent | openhands) ─▶ NormalizedEvent ─▶ path mapping ─▶ events (SQLite)
                                                     navigation (first edit, post-edit, detours) ─▶ edges, baseline, lift ─┤
                                                                                                            ▼
                                                                    unified ranker (weighted | logistic) ─▶ Evidence
                                                                                                            │
                                                         FastAPI (/api/*) + static UI · CLI · Claude Code Stop hook
```

## Package layout (`specweft/`)
| Module | Responsibility |
|---|---|
| `db.py` | SQLite connection, schema migrations (`schema_version`), transactions. |
| `models.py` | Dataclasses: `Occurrence`, `NormalizedEvent`, `Evidence`, `Recommendation`. Shared evidence schema. |
| `tokens.py` | Normalization, version suffix, template normalization, stoplist, specificity. |
| `extract/` | One module per family: `code.py` (tree-sitter py/ts), `config.py` (yaml/json/toml/env), `sql.py` (sqlglot), `contracts.py` (openapi/proto/graphql/avro), `infra.py` (terraform/k8s/docker/ci), `markdown.py`. `registry.py` dispatches by path. |
| `scanner.py` | Walk repo (git-tracked files), exclusions, call extractors, persist occurrences per repo atomically. |
| `agreements.py` | Score tokens (rarity/spread/specificity) and build `agreement_tokens`; holder lookup. |
| `diffs.py` | Unified-diff parser; removed/rename/value-change detection; agreement candidates with dual locations. |
| `replay.py` | Historical commit replay at a cutoff, P@5/R@10/cross-repo share, co-change baseline. |
| `traces/` | `claude_code.py`, `swe_agent.py`, `openhands.py` adapters; `classify.py` (command → event kind); `paths.py` (repo-relative + commit-aware mapping); `ingest.py`. |
| `navigation.py` | Sequencing, first edit, post-edit navigation, detours, edges, baseline, lift, nav score, gold-patch eval. |
| `ranker.py` | Feature assembly, weighted fusion, logistic regression training, confidence, explanations. |
| `api.py` | FastAPI app + static frontend (`web/index.html`). |
| `hook.py` | Claude Code Stop hook entry point. |
| `cli.py` | `specweft scan|index|analyze|ingest|navigate|rank|replay|eval-gold|train|serve`. |

## Database schema (SQLite)
* `repos(id PK, name UNIQUE, root, head_sha, scanned_at)`
* `files(id PK, repo_id FK, path, UNIQUE(repo_id,path))`
* `occurrences(id PK, file_id FK, token_raw, token_norm, base, version, kind, extractor, line, col, context)` — idx on `token_norm`, `file_id`.
* `agreement_tokens(token_norm PK, n_files, n_repos, n_extractors, rarity, spread, specificity, score)`
* `sessions(id PK, source, external_id, repo_id FK NULL, repo_name, commit_sha, started_at, UNIQUE(source,external_id))`
* `events(id PK, session_id FK, seq, kind, path, raw_path, excerpt, ts, UNIQUE(session_id,seq))` — idx on `(path)`.
* `nav_edges(repo_name, src, dst, n_sessions, n_detour, lift, score, last_ts, PK(repo_name,src,dst))`
* `nav_baseline(repo_name, path, n_sessions, rate, PK(repo_name,path))`
* `cochange(repo_name, a, b, n, PK(repo_name,a,b))` — git co-change counts (baseline).
* `replay_labels(id PK, run, repo_name, seed, candidate, features JSON, label)` — training data for LR.
* `models(name PK, params JSON, trained_at, n_samples, metrics JSON)`.

## Scoring (documented formulas)
* rarity = `log((N_files+1)/(df+1)) / log(N_files+1)` ∈ [0,1].
* spread = `min(1, log2(1+n_files)/4 × (1.5 if n_repos>1 else 1))`, 0 for single-file tokens.
* specificity ∈ [0,1] from shape (`tokens.specificity`): separators, length, digits/case, path/URL shape; 0 for stoplisted.
* agreement token score = `rarity^0.5 * specificity * spread`; only tokens with ≥2 files.
* candidate agreement score for file B = `1 - Π(1 - s_t)` over tokens t linking change → B (noisy-or), × change-type weight (removed/rename 1.0, value-change 0.8, touched 0.5).
* navigation: `P(B|A) = (n_AB + α·base_B)/(n_A + α)`, α=1; lift = `P(B|A)/base_B`; score = `(1-exp(-n_AB/2)) * clip(log2(lift)/4, 0, 1)` with detour bonus `+0.1·min(n_detour,3)` capped at 1.
* fused (weighted): `0.55·agree + 0.35·nav + 0.05·recency + 0.05·detours`, ×1.25 (capped 1) if both signals > 0.
  `cross_repo` has weight 0 here (replay showed no benefit; the LR learns a negative weight) but is shown as a flag.
* confidence: `high` if both signals present (dual-signal); `medium` if one signal ≥ 0.5 or the holder still references a
  token the change removed/renamed/changed the value of (a definite break); else `low`.
* logistic regression: trained on replay + gold labels when ≥ 40 labels with both classes exist; **activated** only if
  its temporal-holdout AUC beats the weighted rule, and only applied to candidates whose non-zero features all varied in
  training. Then `confidence_score` = model probability (`confidence_basis: logistic_regression`); otherwise it is the
  weighted score (`uncalibrated_weighted`).
* workspace groups: `repos.group_name` (migration v2). Holders are only looked up inside the changed repo's group, so
  unrelated repositories never produce "cross-repo" agreements through generic shared vocabulary.

## Error handling / logging
* Extractor failures are logged per file and counted in scan stats; never abort a scan.
* DB writes per repo inside `BEGIN … COMMIT`; failure rolls back that repo only.
* API returns 4xx for validation errors, 500 with message otherwise. Hook catches everything → exit 0 + stderr note.
* `logging` module, level via `SPECWEFT_LOG`.

## Testing architecture
`tests/` — unit (tokens, extractors, diff parser, adapters, navigation math, ranker), integration (scan→index→analyze,
ingest→navigate→rank), e2e (API with TestClient, hook via subprocess with a real transcript), edge cases.
