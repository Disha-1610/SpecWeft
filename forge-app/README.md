# SpecWeft for Bitbucket (Forge app)

A Forge app for **Bitbucket Cloud** that shows, on every pull request, the **unchanged files the PR probably
breaks**. For each file it gives evidence: the shared contract token (with both source locations) and how often
coding agents went on to edit that file after editing the changed one. An optional **merge check** fails only on
high-confidence findings, where both signals agree.

```
Bitbucket PR page ──► PR overview panel (UI Kit) ──invoke──► resolver (Forge function)
                                                              │ api.asApp().requestBitbucket: repo + PR diff
                                                              └ invokeRemote('specweft-backend') ──► SpecWeft Python backend
Merge (on-code-pushed) ──► merge-check function ─────────────┘   POST /forge/analyze-pr | /forge/merge-check
                                                                  verifies the Forge Invocation Token (JWT, JWKS)
```

| Piece | File |
|---|---|
| Manifest: PR panel, merge check, remote, scopes | `manifest.yml` |
| Resolver, merge-check handler, Bitbucket + backend calls | `src/index.js` |
| Core logic (pure, unit-tested) | `src/specweft.js`, `test/specweft.test.mjs` |
| UI (UI Kit: DynamicTable, Lozenge, SectionMessage) | `src/frontend/index.jsx` |
| Backend endpoints + token verification | `../specweft/forge.py`, tests in `../tests/test_forge.py` |

## Verified so far

* `manifest.yml` validates against Forge's own manifest JSON schema (`@forge/manifest`): 0 errors. Both scopes
  appear in Forge's scope mapping.
* Every UI Kit component and `@forge/api` function used exists in the installed packages. The Lozenge appearance
  values match the type definitions.
* Node tests for the core logic pass: `npm test`.
* Backend tests pass: `pytest tests/test_forge.py`. Real RS256 tokens are checked for audience, issuer, expiry and
  app id; also covered are unknown repos, the repo mapping, merge-check blocking only on high confidence, and failing
  closed when misconfigured.
* On-demand indexing is tested end to end through a real `git clone` of a local mirror. Also tested: failed and private
  repos are reported and never block merges, and unsafe repo names are rejected.
* **Not yet verified:** `forge lint`/`deploy` and the app running inside Bitbucket. Both need your Atlassian login.
  The SectionMessage `success` appearance is an Atlassian Design System value that is not in the bundled types; check
  it during the first deploy.

## 1. Host the backend (public HTTPS)

Forge Remote calls your backend over HTTPS, and it must answer within **25 s** for the PR panel. Use any container host
that terminates TLS (Render, Fly.io, Railway, a VM with Caddy, …):

```powershell
docker build -t specweft-backend .
```

Run it with a persistent `/data` volume and these environment variables: `SPECWEFT_FORGE_APP_ID` (set it after step 2),
and optionally `SPECWEFT_REPO_MAP`. Check it is reachable: `https://<host>/api/health`.

## 2. Register and configure the Forge app

```powershell
npm install -g @forge/cli
forge login
cd forge-app
npm install
forge register
```

`forge register` writes your app id into `manifest.yml`. Copy that id into the backend's `SPECWEFT_FORGE_APP_ID` and
restart the backend. Then set `remotes[0].baseUrl` in `manifest.yml` to your backend URL.

## 3. Repositories are indexed on demand

When a PR panel opens in a repository SpecWeft hasn't seen, the backend clones it (public HTTPS, no credentials) and
builds its index in the background. The panel shows "Indexing this repository" and refreshes every 5 s until the
results appear. On the demo repo this takes about 4 s. Indexes older than `SPECWEFT_INDEX_TTL_HOURS` (default 24) are
refreshed in the background, and the current results stay visible meanwhile.

Limits, all configurable in `.env.example`:

* **Size:** repos over `SPECWEFT_MAX_REPO_MB` (300) are skipped.
* **Time:** clones time out after `SPECWEFT_CLONE_TIMEOUT` (180 s).
* **History:** `SPECWEFT_CLONE_DEPTH` (500 commits) is kept.
* **Concurrency:** `SPECWEFT_INDEX_WORKERS` (2) jobs run in parallel.

**Private repositories cannot be indexed on demand** because the backend holds no Bitbucket credentials. The panel says
so. An operator can index one manually:

```powershell
python -m specweft.cli --db /data/specweft.db scan /data/repos/<repo> --name <workspace>/<repo> --group <workspace>
```

Navigation evidence (agent trajectories) is optional:

```powershell
python -m specweft.cli --db /data/specweft.db ingest claude_code <dir-with-transcripts>
```

Without trajectories for a repo, every finding comes from agreements alone, so confidence stays medium or low and the
merge check never fails.

## 4. Deploy, install, share

```powershell
forge lint
forge deploy -e production
forge install --product bitbucket --environment production
```

Then share it: developer console → your app → **Distribution** → *Distribution controls* → Edit → **Sharing**. Fill in
the app details, choose Bitbucket, save, and copy the **installation link** for the judges. "Generate new link"
invalidates the old one.

Merge check: a workspace admin enables *Custom merge checks* in workspace settings, then adds
"SpecWeft contract check" at workspace, project or repo level. Mark it **Required** if a failure should block merges.

## Demo repository (publish once)

`demo/specweft-demo` (in the SpecWeft folder, not tracked by SpecWeft's git) is fastapi/full-stack-fastapi-template
(MIT) at the commit **before** upstream PR #2184, with full history. Branch `specweft-demo/database-url` applies
**only** that PR's `backend/app/core/config.py` change. The PR removed the `POSTGRES_*` settings, so the other files
the real PR changed now hold a broken contract.

Create an **empty, public** repository `specweft-demo` in your Bitbucket workspace, then:

```powershell
cd demo/specweft-demo
git remote add origin https://bitbucket.org/<your-workspace>/specweft-demo.git
git push -u origin main specweft-demo/database-url
```

Open a pull request from `specweft-demo/database-url` into `main`, and leave it open for the judges.

## Instructions for judges (paste into the submission)

1. Open the **installation link** and install SpecWeft into a Bitbucket workspace you administer.
2. Fastest path: open the prepared pull request at
   `https://bitbucket.org/<your-workspace>/specweft-demo/pull-requests/1`. The **SpecWeft** panel on the PR overview
   lists the files the change breaks, with evidence.
   To try it in your own workspace instead:
   - Import the public repo: *Create → Repository → Import repository* with
     `https://bitbucket.org/<your-workspace>/specweft-demo.git`.
   - Create a PR from `specweft-demo/database-url` into `main`.
   - The first time, the panel shows "Indexing this repository" for a few seconds.
3. Expected result: the change only edits `backend/app/core/config.py`. SpecWeft lists `.env`, `compose.yml`,
   `deployment.md`, `backend/app/alembic/env.py` and `backend/app/core/db.py`, which are exactly the files upstream
   PR #2184 had to change, plus README/deploy workflows that still reference the removed `POSTGRES_PASSWORD`. Each
   finding shows the removed token, where it was removed, and the line that still holds it.
4. Also works on any **public** repository: open any PR there.
5. Optional merge check: *Workspace settings → Custom merge checks* → enable "SpecWeft contract check".

Verified locally with the backend's real code path: the demo repo was cloned and indexed in 4.2 s (209 files), the
analysis took 1.8 s, and all 5 upstream-PR files appeared in the top 8.

## Explanation for the submission (technology requirement)

SpecWeft is a Forge app integrated with **Bitbucket Cloud**. It uses two Bitbucket Forge modules:
`bitbucket:repoPullRequestOverviewPanel` (a UI Kit panel on every pull request) and `bitbucket:mergeCheck` (runs on
`on-code-pushed`). It reads the pull request and repository through the Bitbucket REST API
(`api.asApp().requestBitbucket`, scopes `read:pullrequest:bitbucket` and `read:repository:bitbucket`). Analysis runs on
a **Forge Remote** backend called with `invokeRemote`. Every request is authenticated with a Forge Invocation Token,
which the backend verifies against Atlassian's JWKS (issuer `forge/invocation-token`, audience = app id) before doing
any work.
