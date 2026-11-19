# SpecWeft — Project Requirements

SpecWeft predicts **which other files must change when a file changes**, by fusing two independent signals:

* **Broken Agreements** (static): implicit contracts — the same rare, specific token (env var, route, table, topic,
  proto field, config key …) appearing in several files/repos. Changing or removing it in one place breaks the others.
* **Waze for Code** (behavioural): agent/developer trajectories (Claude Code, SWE-agent, OpenHands). After editing file A,
  where did agents navigate next, and where did they detour after a failing test/build?

## Functional requirements

| ID | Requirement |
|----|-------------|
| BA-1 | Scan multiple git repositories (path list), respecting exclusions (vendor, node_modules, build dirs, binaries, size cap). |
| BA-2 | Python + TypeScript/TSX extraction via tree-sitter (string literals, identifiers of definitions, attribute/property keys). |
| BA-3 | YAML, JSON, TOML, `.env` parsing (keys and scalar values with line numbers). |
| BA-4 | SQL + migrations via sqlglot (tables, columns); Alembic/Django-style migration files picked up through Python + SQL. |
| BA-5 | OpenAPI (paths, operationIds, schema names, properties), Protobuf (package, message, field, service, rpc), GraphQL (types, fields), Avro (record/field names). |
| BA-6 | Terraform (resource types/names, variables, string values), Kubernetes (kind/name/env/ports/images/labels), Dockerfile (ENV/ARG/EXPOSE/FROM), CI (GitHub Actions/GitLab job names, env, secrets). |
| BA-7 | Markdown inline-code (`` `token` ``) extraction. |
| BA-8 | Store each occurrence with repo, path, line, column, kind, extractor, raw text, commit SHA. |
| BA-9 | Token normalization (case/separator folding: `userId`, `USER_ID`, `user-id` → `user_id`). |
| BA-10 | Version-suffix extraction (`orders_v2`, `/v1/orders`, `OrderV3` → base + version). |
| BA-11 | Template/pattern normalization (`/users/{id}`, `/users/:id`, `` `/users/${id}` ``, `%s`) → `{}` placeholders. |
| BA-12 | Rarity (IDF across files), spread (files, repos, extractors), specificity (shape) scoring. |
| BA-13 | Stoplist + exclusion handling (generic words, language keywords, short/numeric tokens, configurable). |
| BA-14 | Agreement index: tokens held by ≥2 files with combined score, persisted in SQLite. |
| BA-15 | PR diff analysis from a unified diff (git commit/range or file). |
| BA-16 | Removed-token detection. |
| BA-17 | Rename detection (removed token paired with added token in same hunk/line context). |
| BA-18 | Value-change detection (config key whose value changed). |
| BA-19 | Holder detection across files and across repositories. |
| BA-20 | Evidence with both source locations (changed site and holder site). |
| BA-21 | Historical PR (commit) replay with leakage-free index built at a cutoff commit. |
| BA-22 | Precision@5, Recall@10, cross-repo share metrics. |
| BA-23 | Git co-change baseline comparison on the same replay set. |
| WZ-1..3 | Adapters: Claude Code JSONL, SWE-agent trajectories, OpenHands trajectories (separate adapters → one schema). |
| WZ-4..5 | Normalized event schema with kinds `search, read, edit, test_run, test_fail, build_fail` (+ `build_run`). |
| WZ-6..7 | Repository-relative path mapping; commit-aware mapping (path at session commit → path at HEAD via git rename detection). |
| WZ-8 | Event sequencing (stable per-session order). |
| WZ-9 | First-edit identification. |
| WZ-10 | Post-edit navigation analysis (files read/edited after an edit, within a window). |
| WZ-11 | Detour detection after test/build failures. |
| WZ-12 | Navigation edges A→B persisted. |
| WZ-13..15 | Baseline visit rate, lift, navigation score. |
| WZ-16 | Evidence with session counts and excerpts. |
| WZ-17 | Gold-patch evaluation (resolved patches as gold). |
| WZ-18 | Comparison against co-change predictions. |
| UR-1..10 | Unified ranker: features (agreement, navigation, cross-repo, detours, recency), weighted fusion, logistic regression when enough replay labels, confidence levels, evidence, explanations. Dual-signal agreement boosts confidence. |
| EV-1 | Shared evidence schema used by API, frontend, CLI and hook. |
| CC-1 | Claude Code Stop hook: reads hook input, derives edited files from transcript, queries ranker, returns actionable evidence, never crashes/blocks on failure, blocks at most once (`stop_hook_active`). |

## Non-functional
* Local, offline-capable; SQLite single file; Python 3.11+.
* Deterministic, repeatable scans (re-scan of a repo replaces its occurrences in one transaction).
* All external input validated (API via pydantic; CLI via argparse; hook tolerant to malformed JSON).
* Failures are reported, never masked as success.

## Data sources (real)
* Repos: `fastapi/full-stack-fastapi-template`, `GoogleCloudPlatform/microservices-demo` (cloned into `data/repos`).
* Trajectories: HF `nebius/SWE-agent-trajectories`, `nebius/SWE-rebench-openhands-trajectories` (rows API samples), and the
  local Claude Code transcripts in `~/.claude/projects`.

## Open points / assumptions
* "Gold patch" for the trajectory datasets = the patch of a trajectory marked resolved (`target`/`resolved`), since the
  datasets do not ship the official SWE-bench gold patch. Documented in evaluation output.
* "Historical fixes" for replay = files co-changed in the same commit (the commit is the fix unit for non-PR history).
