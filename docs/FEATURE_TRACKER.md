# Feature Tracker

Status meanings: **VERIFIED** = implemented, covered by automated tests, and exercised on real data by the integrated
pipeline (`python -m specweft.cli pipeline`). **TESTED** = implemented and tested, but not fully verified in its
intended live environment. **BLOCKED** = cannot be completed without something outside this environment.

## A. Broken Agreements

| # | Feature | Status | Where | Evidence |
|---|---|---|---|---|
| 1 | Multi-repository scanning | VERIFIED | `scanner.py` | 5 real repos scanned (template, sqlmodel, microservices-demo, cognitive_complexity@PR-base, SpecWeft); `test_scan_*` |
| 2 | Python + TypeScript via tree-sitter | VERIFIED | `extract/code.py` | `test_python_tree_sitter`, `test_typescript_template_string`; 43 py + 109 ts/tsx files in template |
| 3 | YAML / JSON / TOML / .env | VERIFIED | `extract/config.py` | `test_config_env_toml_markdown`; JSONC + Helm-template fallbacks (`test_helm_template_and_jsonc_are_tolerated`) |
| 4 | SQL + migrations via sqlglot | VERIFIED | `extract/sql.py` | `test_sql_sqlglot` (tables, columns, line numbers); Alembic migrations via Python extractor |
| 5 | OpenAPI / Protobuf / GraphQL / Avro | VERIFIED | `extract/contracts.py` | `test_contracts`; 8 real `.proto` files in microservices-demo |
| 6 | Terraform / Kubernetes / Docker / CI | VERIFIED | `extract/infra.py` | `test_infra`; 73 k8s, 9 terraform, 13 Dockerfiles, 24 CI files in real repos |
| 7 | Markdown inline code | VERIFIED | `extract/markdown.py` | fenced blocks skipped (`test_config_env_toml_markdown`) |
| 8 | Occurrences with full location metadata | VERIFIED | `occurrences` table | repo, path, line, col, kind, extractor, raw, context; `test_scan_stores_locations_and_dedups` |
| 9 | Token normalization | VERIFIED | `tokens.normalize` | `test_case_and_separator_folding` |
| 10 | Version-suffix extraction | VERIFIED | `tokens.normalize` | `test_version_suffix_identifier_and_path` |
| 11 | Template / pattern normalization | VERIFIED | `tokens.normalize_template` | `{id}`, `:id`, `${id}`, `<int:id>`, `%s` → `{}`; Python route, OpenAPI path and TS template string agree in fixture |
| 12 | Rarity, spread, specificity | VERIFIED | `tokens.py`, `agreements.build_index` | formulas in SYSTEM_ARCHITECTURE.md; `test_scores_bounds`, `test_index_scores_cross_repo_contract` |
| 13 | Stoplist + exclusions | VERIFIED | `tokens.STOPWORDS`, `scanner.EXCLUDED_DIRS`, `--exclude` | language/stdlib vocabulary removed programmatically after the real PR demo showed `build`/`startswith` noise |
| 14 | Agreement index | VERIFIED | `agreement_tokens` | built over 840 real files (2,594 tokens) |
| 15 | PR diff analysis | VERIFIED | `diffs.parse_unified_diff` | count-driven hunk parsing; `test_parse_diff_handles_header_like_content` |
| 16 | Removed-token detection | VERIFIED | `diffs.detect_changes` | `test_detect_removed_and_deleted_file`; real PR #2184 (`postgres_password` removed) |
| 17 | Rename detection | VERIFIED | `diffs.detect_changes` | aligned token replacement; `test_detect_rename_and_value_change` |
| 18 | Value-change detection | VERIFIED | `diffs.detect_changes` | `KEY=old` → `KEY=new`; `test_detect_rename_and_value_change` |
| 19 | Cross-file / cross-repo holders | VERIFIED | `agreements.holders` (+ workspace groups) | `test_analyze_diff_finds_cross_repo_holders_with_both_locations`, `test_groups_isolate_unrelated_repos` |
| 20 | Evidence with both locations | VERIFIED | `AgreementEvidence.changed_site/holder_site` | API test asserts both line numbers |
| 21 | Historical PR replay | VERIFIED | `evaluation.replay` | leakage-free cutoff index; 120 commits × 2 real repos; `test_replay_end_to_end_on_fixture_history` |
| 22 | P@5, R@10, cross-repo share | VERIFIED | `evaluation.metrics` | `test_metrics`; reports in `data/reports/` |
| 23 | Git co-change baseline | VERIFIED | `cochange.py` | online (past-only) updates during replay; `test_cochange_counts_and_prediction` |

## B. Waze for Code

| # | Feature | Status | Where | Evidence |
|---|---|---|---|---|
| 1 | Claude Code JSONL parsing | VERIFIED | `traces/claude_code.py` | 58 real local transcripts ingested; `test_claude_code_adapter` |
| 2 | SWE-agent ingestion | VERIFIED | `traces/swe_agent.py` | 100 real rows (nebius/SWE-agent-trajectories); `test_real_swe_agent_rows_parse` |
| 3 | OpenHands ingestion | VERIFIED | `traces/openhands.py` | 60 real rows (nebius/SWE-rebench-openhands-trajectories); `test_real_openhands_rows_parse` |
| 3b | Bitbucket PR history as navigation | VERIFIED | `traces/bitbucket_pr.py`, `navigation.analyze_pr_session`, `POST /forge/pr-history`, Forge `syncPrHistory` | commit order → edges, reviewer comments → detours; `tests/test_pr_history.py` (reaches `high` with agreement), JS sync tests |
| 4 | Normalized event schema | VERIFIED | `models.NormalizedEvent`, `events` table | rejects unknown kinds |
| 5 | search/read/edit/test-run/test-fail/build-fail | VERIFIED | `traces/classify.py` | all kinds observed in real data (incl. 380+ test_fail) |
| 6 | Repo-relative path mapping | VERIFIED | `traces/paths.to_repo_relative` | Windows, MSYS (`/c/...`), container (`/workspace/x`) paths; `test_path_mapping` |
| 7 | Commit-aware path mapping | VERIFIED | `traces/paths.commit_at/rename_map` | session commit by timestamp, renames to HEAD; `test_commit_aware_mapping` |
| 8 | Event sequencing | VERIFIED | `events.seq` (UNIQUE per session) | |
| 9 | First-edit identification | VERIFIED | `navigation.analyze_session` | used as gold-eval seed |
| 10 | Post-edit navigation | VERIFIED | `navigation.analyze_session` | window of 15 events |
| 11 | Detours after test/build failure | VERIFIED | `navigation.analyze_session` | `test_navigation_edges_lift_and_detours` |
| 12 | Navigation edges | VERIFIED | `nav_edges` | 6.4k edges from 213 real sessions |
| 13 | Baseline visit rate | VERIFIED | `nav_baseline` | |
| 14 | Lift | VERIFIED | `navigation.nav_score` | asserted against the closed-form formula |
| 15 | Navigation score | VERIFIED | `navigation.nav_score` | `test_nav_score_properties` |
| 16 | Evidence with session counts + excerpts | VERIFIED | `NavigationEvidence` | |
| 17 | Gold-patch evaluation | VERIFIED (caveat) | `evaluation.gold_eval` | real data only allows leave-one-*trajectory*-out (all 45 trajectories solve one instance); labelled optimistic |
| 18 | Comparison vs co-change | VERIFIED | `evaluation.gold_eval` | co-change from history before the PR base |

## C. Unified ranker / D. Evidence / E. Claude Code integration

| Feature | Status | Evidence |
|---|---|---|
| Agreement, navigation, cross-repo, detours, recency features | VERIFIED | `ranker.rank`; recency leakage found and fixed (strict `--before`, committer time) |
| Weighted ranking + dual-signal boost | VERIFIED | `test_rank_fuses_and_dual_signal_is_high_confidence` |
| Logistic regression with sufficient labels | VERIFIED | refuses below 40 labels / single class; activated only when temporal-holdout AUC beats the weighted rule; never applied to features unseen in training |
| Confidence levels + explanations | VERIFIED | high = both systems, medium = one strong, low otherwise; `confidence_basis` says whether calibrated |
| Shared evidence schema (API, UI, CLI, hook) | VERIFIED | all interfaces serialize `models.Recommendation` |
| REST API + web UI | VERIFIED | `test_api_hook.py` (TestClient); UI checked in browser |
| Stop hook: input, edited files, ranker query, evidence, safe failure, block-once | VERIFIED | subprocess tests; run on this session's real transcript |
| Stop hook inside a live Claude Code session | VERIFIED | `scripts/verify_hook_live.ps1` (Claude Code 2.1.193): Claude renamed `PROJECT_NAME` in config.py; Stop hook fired (status ok, 1.0 s) and returned a non-blocking message listing 13 files still holding `project_name` |
| Finish-line guardrail: `specweft check` (working tree vs base, exit 1 on fail, shared `SPECWEFT_FAIL_ON` with the hook) and `specweft agent-demo` | VERIFIED | `tests/test_guardrail.py`: hook blocks the demo agent once for files in 2 other repos; check exit codes 1/0 |
