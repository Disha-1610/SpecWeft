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

## 3. Index the repositories the judges will use

The backend must have scanned each Bitbucket repo that PRs will be opened in. The scanned name must equal the Bitbucket
repo slug, or be mapped with `SPECWEFT_REPO_MAP`. On the backend host:

```powershell
git clone https://bitbucket.org/<workspace>/<repo>.git /data/repos/<repo>
python -m specweft.cli --db /data/specweft.db scan /data/repos/<repo> --name <repo> --group <workspace>
python -m specweft.cli --db /data/specweft.db ingest claude_code <dir-with-transcripts>
```

The ingest step is optional but enables the navigation signal and "high" confidence. Re-scan after merges to keep the
index current.

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

## Recommended demo setup for judges

1. Create a Bitbucket workspace. Import `fastapi/full-stack-fastapi-template` (and `fastapi/sqlmodel`) at the
   commit **before** PR #2184 (`32ab6dd^`).
2. Index both repos on the backend (step 3) with one `--group`.
3. Open a PR that reproduces PR #2184's `backend/app/core/config.py` change only.
   SpecWeft's panel should list `compose.yml`, `.env`, `deployment.md`, `backend/app/core/db.py` and
   `backend/app/alembic/env.py`, each with "removes `postgres_password` / `sqlalchemy_database_uri` which is still
   held here" evidence. These are the 5 files the real PR had to change.

## Explanation for the submission (technology requirement)

SpecWeft is a Forge app integrated with **Bitbucket Cloud**. It uses two Bitbucket Forge modules:
`bitbucket:repoPullRequestOverviewPanel` (a UI Kit panel on every pull request) and `bitbucket:mergeCheck` (runs on
`on-code-pushed`). It reads the pull request and repository through the Bitbucket REST API
(`api.asApp().requestBitbucket`, scopes `read:pullrequest:bitbucket` and `read:repository:bitbucket`). Analysis runs on
a **Forge Remote** backend called with `invokeRemote`. Every request is authenticated with a Forge Invocation Token,
which the backend verifies against Atlassian's JWKS (issuer `forge/invocation-token`, audience = app id) before doing
any work.
