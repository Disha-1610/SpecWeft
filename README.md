# SpecWeft

**When you change a file, which other files must change too — and why?**

SpecWeft answers this with two independent signals fused into one ranked, evidence-backed list:

* **Broken Agreements** (static). Files *agree* when they hold the same rare, specific token: an env var, route,
  table, column, proto field, topic, config key. Removing, renaming or changing the value of that token in one file
  breaks every other holder. Extracted from Python/TypeScript (tree-sitter), YAML/JSON/TOML/.env, SQL (sqlglot),
  OpenAPI/Protobuf/GraphQL/Avro, Terraform/Kubernetes/Docker/CI and Markdown inline code.
* **Waze for Code** (behavioural). Agent trajectories (Claude Code, SWE-agent, OpenHands) show where agents went next
  after editing a file, and where they detoured after a failing test or build. Navigation edges are scored by lift over
  each file's baseline visit rate.

Every recommendation uses one shared evidence schema (`specweft/models.py: Recommendation`): changed file, related
file, reason, agreement evidence with **both** source locations, navigation evidence with session counts and excerpts,
cross-repo flag, features, ranking score, confidence level and confidence basis. The CLI, REST API, web UI and Claude Code
Stop hook all return it.

Docs: [PROJECT_REQUIREMENTS.md](PROJECT_REQUIREMENTS.md) · [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md) (formulas,
schema) · [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) · [FEATURE_TRACKER.md](FEATURE_TRACKER.md) (status of every
requirement).

## Setup

Requires Python ≥ 3.11 and git on PATH. Tested on Python 3.14 / Windows 11.

```powershell
pip install -r requirements.txt
```

Optional configuration: copy `.env.example` values into your environment (`SPECWEFT_DB`, `SPECWEFT_HOOK_MODE`, …).
The SQLite database is created and migrated automatically on first use (`specweft/db.py`, schema v2).

### Real data used by the pipeline

```powershell
git clone https://github.com/fastapi/full-stack-fastapi-template data/repos/full-stack-fastapi-template
git clone https://github.com/fastapi/sqlmodel data/repos/sqlmodel
git clone https://github.com/GoogleCloudPlatform/microservices-demo data/repos/microservices-demo
git clone https://github.com/Melevir/cognitive_complexity data/repos/cognitive_complexity
```

Trajectories (Hugging Face datasets-server rows API, first rows of each dataset):

```powershell
curl.exe -s "https://datasets-server.huggingface.co/rows?dataset=nebius/SWE-agent-trajectories&config=default&split=train&offset=0&length=100" -o data/trajectories/sweagent_rows.json
```

```powershell
curl.exe -s "https://datasets-server.huggingface.co/rows?dataset=nebius/SWE-rebench-openhands-trajectories&config=default&split=train&offset=0&length=60" -o data/trajectories/openhands_rows.json
```

Claude Code transcripts are read from `~/.claude/projects/*/*.jsonl`.

## Run

Complete workflow (scan → index → ingest → navigation → replay/gold evaluation → LR fusion → historical PR demo);
writes `data/specweft.db` and `data/reports/*.json` (about 9 minutes):

```powershell
python -m specweft.cli pipeline
```

API + web UI at http://127.0.0.1:8765:

```powershell
python -m specweft.cli serve
```

Tests (76 tests: unit, integration, end-to-end API/hook subprocess, edge cases, real-data parsing):

```powershell
python -m pytest -q
```

### Individual commands

```powershell
python -m specweft.cli scan path/to/repoA path/to/repoB --group my-system
python -m specweft.cli ingest claude_code $HOME/.claude/projects
python -m specweft.cli ingest swe_agent data/trajectories/sweagent_rows.json
python -m specweft.cli ingest openhands data/trajectories/openhands_rows.json
python -m specweft.cli analyze --repo full-stack-fastapi-template --commit HEAD
git diff | python -m specweft.cli analyze --repo full-stack-fastapi-template --diff -
python -m specweft.cli rank --repo full-stack-fastapi-template --files backend/app/core/config.py
python -m specweft.cli replay data/repos/microservices-demo --max-commits 120
python -m specweft.cli eval-gold --nav-repo Melevir/cognitive_complexity --scanned-repo cognitive_complexity --root data/repos/cognitive_complexity --pr 15
```

`--group` puts repositories that form one system into a workspace group. Cross-repo agreements are only reported inside
a group, so unrelated repos never match through generic vocabulary.

### REST API

| Method | Path | Body / params | Returns |
|---|---|---|---|
| GET | `/api/health` | – | counts, active model |
| GET | `/api/repos` | – | scanned repos |
| GET | `/api/agreements/top` | `limit` | top agreement tokens with rarity/spread/specificity |
| GET | `/api/agreements/holders` | `token` | every holder (repo, path, line) of a normalized token |
| POST | `/api/analyze` | `{repo, diff \| commit, limit}` | token changes + `recommendations[]` |
| POST | `/api/rank` | `{repo, changed_files[], diff?, limit}` | `recommendations[]` |
| GET | `/api/navigation` | `repo, src` | navigation edges from a file |
| GET | `/api/sessions` | `limit` | ingested sessions |
| GET | `/api/reports` | – | evaluation reports |

Invalid input returns 422 with a message (exactly one of `diff`/`commit`; unknown repo; empty diff; bad commit).
OpenAPI docs: `/docs`.

### Claude Code Stop hook

Add to the target project's `.claude/settings.json` (adjust paths):

```json
{"hooks": {"Stop": [{"hooks": [{"type": "command",
  "command": "python C:/path/to/SpecWeft/scripts/specweft_hook.py --db C:/path/to/SpecWeft/data/specweft.db",
  "timeout": 120}]}]}}
```

On Stop, the hook reads the session transcript, finds the files the session edited, and diffs them against `HEAD`
(precise removed/renamed/value-changed tokens). It queries the ranker and reports files the session did not update:

* blocks (`{"decision":"block","reason":…}`) **only** when there is a high-confidence (dual-signal) recommendation,
  **only once** (`stop_hook_active` is respected), and never when `SPECWEFT_HOOK_MODE=warn`;
* otherwise it returns a non-blocking `systemMessage`; with nothing to report it prints nothing;
* any internal failure exits 0 with a stderr note. SpecWeft never breaks a session. Every call is logged to
  `data/hook_log.jsonl`.

To verify it live after `claude /login`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify_hook_live.ps1
```

## Results on real data

From the final `python -m specweft.cli pipeline` run (raw JSON in `data/reports/`).

**Inputs.** 5 repos / 840 files indexed: full-stack-fastapi-template (205 files) and sqlmodel (376, docs excluded) in
group `fastapi-stack`; microservices-demo (200); cognitive_complexity at the PR #15 base (10); SpecWeft (49).
2,594 agreement tokens. 219 trajectories: 100 SWE-agent, 60 OpenHands, 59 local Claude Code sessions, giving
6,378 navigation edges.

**Historical PR demo** (`data/reports/demo_pr.json`). PR #2184 "Migrate to `DATABASE_URL` instead of separate
variables". The index was built at the PR's parent, and SpecWeft got **only** the `backend/app/core/config.py` diff:

| rank | predicted file | changed by the PR? | evidence |
|---|---|---|---|
| 1 | compose.yml | ✅ | removes `postgres_password`, still held here |
| 2 | .env | ✅ | removes `postgres_password` |
| 3 | deployment.md | ✅ | removes `postgres_password` |
| 4–6 | README.md, deploy-production.yml, deploy-staging.yml | ❌ | still hold `POSTGRES_PASSWORD` after the merge (checked with `git show 32ab6dd:<file>`) |
| 7 | backend/app/core/db.py | ✅ | removes `sqlalchemy_database_uri` |
| 8 | backend/app/alembic/env.py | ✅ | removes `sqlalchemy_database_uri` |

Recall@10 = **1.0** (5/5 files), P@10 = 0.5. The ✅/❌ judgement is against what the PR changed. Ranks 4–6
genuinely still reference the removed variable.

**Commit replay** (120 commits after an 80% history cutoff; index and co-change built only from the past;
truth = other files in the same commit):

| repo | method | P@5 | R@10 | cross-repo share |
|---|---|---|---|---|
| full-stack-fastapi-template | agreement | 0.090 | 0.170 | 0.32 |
| | agreement (in-repo predictions only) | 0.134 | 0.182 | 0 |
| | fused (weighted) | 0.087 | 0.167 | 0.33 |
| | **git co-change baseline** | **0.263** | **0.664** | 0 |
| microservices-demo | agreement | 0.242 | 0.475 | 0 |
| | fused (weighted) | 0.244 | 0.473 | 0 |
| | **git co-change baseline** | **0.408** | **0.826** | 0 |

Co-change is the stronger predictor of same-commit co-changes on these repos. The replay has no trajectories for these
repos, so "fused" here is agreement + recency only.

**Logistic fusion.** Trained on 2,186 replay + gold labels (270 positive). It is activated only because the
temporal-holdout AUC beat the weighted rule: 0.801 vs 0.767, the mean over both repos (template 0.809 vs 0.758,
microservices-demo 0.793 vs 0.776). Learned weights: agreement +2.21, navigation +0.99, detours +3.40,
recency +3.76, cross-repo −4.49.

**Gold-patch evaluation** (cognitive_complexity, seed = first gold file the agent edited, navigation from *other*
trajectories; leave-one-trajectory-out because every trajectory solves the same instance, so this is optimistic):

| gold definition | method | n | P@5 | R@10 |
|---|---|---|---|---|
| resolved trajectory patches | navigation | 8 | 0.15 | 0.75 |
| | agreement | 8 | 0.00 | 0.00 |
| | co-change (history before PR base) | 8 | 0.025 | 0.25 |
| upstream PR #15 files | navigation | 17 | 0.20 | **1.00** |
| | co-change | 17 | 0.012 | 0.059 |

With one truth file per seed, the maximum possible P@5 is 0.2.

## Known limitations

* **Agreement vs co-change.** On commit replay, git co-change beats agreements on in-repo precision/recall (see
  results). Agreements are a different signal: they find *contract* holders, including files that never co-changed
  before. Co-change cannot see those, and the PR demo shows them. Same-commit truth also cannot credit correct
  cross-repo predictions, so the cross-repo share is reported but cannot be scored as hits.
* **Gold-patch evaluation is optimistic.** All 45 real `cognitive_complexity` trajectories in the downloaded sample solve
  the same instance, so navigation is evaluated leave-one-*trajectory*-out (other agents on the same task), not
  leave-one-instance-out. The report labels this. Larger per-repo samples need the HF `filter` endpoint, which was
  failing with a server-side auth error during development.
* **"Gold" for trajectory datasets** = files of the resolved patch that exist in the repo (the datasets don't ship
  the SWE-bench gold patch). The upstream-PR variant uses the real merged PR (#15) instead.
* **Index snapshot.** Replay indexes the repo once at the cutoff. Files that changed later are matched against their
  cutoff content.
* **Regex-based extractors** for Protobuf, GraphQL, Terraform and Dockerfile cover the common syntax, not full grammars.
  Helm templates are de-templated heuristically before YAML parsing.
* **Hook live test** passed with Claude Code 2.1.193 (`scripts/verify_hook_live.ps1`). The blocking path (high-confidence,
  dual-signal) is covered by tests; in that live run there was no navigation data for the sandbox, so the hook warned rather than blocked.
* Confidence scores are calibrated probabilities only when the LR is active (`confidence_basis`). Otherwise they are
  an uncalibrated weighted score and are labelled that way.
