"""Forge Remote endpoints: FIT verification with a locally generated RS256 key (stand-in for Atlassian's JWKS)."""
import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from specweft import api, forge
from tests.test_scan_index_diff import DIFF_RENAME

APP_ID = "ari:cloud:ecosystem::app/00000000-0000-0000-0000-000000000000"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


class _Key:
    key = KEY.public_key()


class _Client:
    def get_signing_key_from_jwt(self, token):
        return _Key()


def token(**over):
    now = int(time.time())
    claims = {"iss": "forge/invocation-token", "aud": APP_ID, "iat": now, "nbf": now, "exp": now + 25,
              "app": {"id": APP_ID, "installation": {"id": "inst"}}} | over
    return jwt.encode(claims, KEY, algorithm="RS256", headers={"kid": "k1"})


@pytest.fixture()
def client(indexed, monkeypatch):
    monkeypatch.setenv("SPECWEFT_FORGE_APP_ID", APP_ID)
    monkeypatch.delenv("SPECWEFT_FORGE_AUTH", raising=False)
    monkeypatch.setattr(forge, "_jwks_client", lambda url: _Client())
    api.app.state.db_path = indexed.execute("PRAGMA database_list").fetchone()[2]
    yield TestClient(api.app)
    del api.app.state.db_path


BODY = {"repo_slug": "backend", "repo_full_name": "ws/backend", "pr_id": 7, "diff": DIFF_RENAME}


def test_analyze_pr_with_valid_token(client):
    r = client.post("/forge/analyze-pr", json=BODY, headers={"Authorization": f"Bearer {token()}"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["repo"] == "backend" and j["changed_files"] == ["app/settings.py"]
    paths = {x["related_file"]["path"] for x in j["recommendations"]}
    assert "deploy/k8s.yaml" in paths and "app/settings.py" not in paths
    assert j["summary"]["total"] == len(j["recommendations"])


@pytest.mark.parametrize("hdr", [None, "Bearer garbage", f"Bearer {{}}"])
def test_rejects_missing_or_bad_token(client, hdr):
    h = {"Authorization": hdr} if hdr else {}
    assert client.post("/forge/analyze-pr", json=BODY, headers=h).status_code == 401


@pytest.mark.parametrize("over", [{"aud": "ari:cloud:ecosystem::app/other"}, {"iss": "someone"},
                                  {"exp": int(time.time()) - 100}, {"app": {"id": "ari:cloud:ecosystem::app/other"}}])
def test_rejects_wrong_claims(client, over):
    r = client.post("/forge/analyze-pr", json=BODY, headers={"Authorization": f"Bearer {token(**over)}"})
    assert r.status_code == 401


def test_repo_map(client, monkeypatch):
    h = {"Authorization": f"Bearer {token()}"}
    monkeypatch.setenv("SPECWEFT_REPO_MAP", '{"ws/orders-api": "backend"}')
    r = client.post("/forge/analyze-pr", json=BODY | {"repo_slug": "orders-api", "repo_full_name": "ws/orders-api"},
                    headers=h)
    assert r.status_code == 200 and r.json()["repo"] == "backend"


def test_merge_check(client):
    from tests.test_ranker_eval import _nav
    import sqlite3
    h = {"Authorization": f"Bearer {token()}"}
    r = client.post("/forge/merge-check", json=BODY, headers=h).json()
    assert r["success"] is True  # agreement-only findings never block
    conn = sqlite3.connect(api.app.state.db_path)
    conn.row_factory = sqlite3.Row
    from specweft import db
    _nav(db.connect(api.app.state.db_path), "backend", "app/settings.py", "deploy/k8s.yaml")
    r = client.post("/forge/merge-check", json=BODY, headers=h).json()
    assert r["success"] is False and "deploy/k8s.yaml" in r["message"]
    r = client.post("/forge/merge-check", json=BODY | {"repo_slug": "nope", "repo_full_name": "x/nope",
                                                        "is_private": True}, headers=h).json()
    assert r["success"] is True and "skipped" in r["message"]


def test_misconfigured_server_fails_closed(client, monkeypatch):
    monkeypatch.delenv("SPECWEFT_FORGE_APP_ID")
    r = client.post("/forge/analyze-pr", json=BODY, headers={"Authorization": f"Bearer {token()}"})
    assert r.status_code == 500


# ---------------------------------------------------------------- on-demand indexing

class _SyncPool:
    def submit(self, fn, *a):
        fn(*a)


@pytest.fixture()
def mirror(tmp_path, repos, monkeypatch):
    """A local bare mirror standing in for bitbucket.org: <base>/acme/orders.git is the fixture backend repo."""
    from tests.conftest import git
    from specweft import indexer
    base = tmp_path / "mirror"
    (base / "acme").mkdir(parents=True)
    git(tmp_path, "clone", "-q", "--bare", str(repos["backend"]), str(base / "acme" / "orders.git"))
    monkeypatch.setenv("SPECWEFT_GIT_BASE", base.as_uri())
    monkeypatch.setenv("SPECWEFT_REPOS_DIR", str(tmp_path / "clones"))
    monkeypatch.setattr(indexer, "_pool", _SyncPool())
    return base


ORDERS = {"repo_slug": "orders", "repo_full_name": "acme/orders", "pr_id": 1, "diff": DIFF_RENAME}


def test_unknown_public_repo_is_indexed_on_demand(client, mirror):
    h = {"Authorization": f"Bearer {token()}"}
    first = client.post("/forge/analyze-pr", json=ORDERS, headers=h).json()
    # synchronous pool: the job ran during the request, so it reports indexing then completes
    assert first["status"] == "indexing" and first["job"]["status"] in ("queued", "done")
    st = client.get("/forge/index-status", params={"repo_full_name": "acme/orders"}, headers=h).json()
    assert st["job"]["status"] == "done" and st["job"]["files"] > 5
    second = client.post("/forge/analyze-pr", json=ORDERS, headers=h).json()
    assert second["status"] == "ready" and second["repo"] == "acme/orders"
    assert any(r["related_file"]["path"] == "deploy/k8s.yaml" for r in second["recommendations"])


def test_failed_clone_is_reported_not_retried_forever(client, mirror):
    h = {"Authorization": f"Bearer {token()}"}
    body = ORDERS | {"repo_slug": "ghost", "repo_full_name": "acme/ghost"}
    r = client.post("/forge/analyze-pr", json=body, headers=h).json()
    assert r["status"] in ("indexing", "failed")
    r = client.post("/forge/analyze-pr", json=body, headers=h).json()
    assert r["status"] == "failed" and r["error"]
    m = client.post("/forge/merge-check", json=body, headers=h).json()
    assert m["success"] is True and "skipped" in m["message"]


def test_private_repo_is_uploaded_not_cloned(client, mirror, tmp_path):
    import base64
    from pathlib import Path
    h = {"Authorization": f"Bearer {token()}"}
    body = ORDERS | {"is_private": True, "repo_full_name": "acme/secret", "repo_slug": "secret"}
    r = client.post("/forge/analyze-pr", json=body, headers=h).json()
    assert r["status"] == "needs_upload"
    assert client.get("/forge/index-status", params={"repo_full_name": "acme/secret"}, headers=h).json()["job"] is None
    files = {"app/settings.py": b"POSTGRES_PASSWORD = 'y'\n", "deploy/k8s.yaml": b"env:\n  - name: POSTGRES_PASSWORD\n"}
    up = {"repo_full_name": "acme/secret", "commit": "a" * 40, "manifest": sorted(files)}
    st = client.post("/forge/upload", json=up | {"files": []}, headers=h).json()
    assert st["missing"] == sorted(files) and st["job"] is None
    first = {"path": "app/settings.py", "content_b64": base64.b64encode(files["app/settings.py"]).decode()}
    st = client.post("/forge/upload", json=up | {"files": [first]}, headers=h).json()
    assert st["missing"] == ["deploy/k8s.yaml"] and st["received"] == 1
    rest = {"path": "deploy/k8s.yaml", "content_b64": base64.b64encode(files["deploy/k8s.yaml"]).decode()}
    st = client.post("/forge/upload", json=up | {"files": [rest]}, headers=h).json()
    assert st["missing"] == [] and st["job"]["status"] == "done", st
    r = client.post("/forge/analyze-pr", json=body, headers=h).json()
    assert r["status"] == "ready" and r["repo"] == "acme/secret"


@pytest.mark.parametrize("path", ["../x", "/etc/passwd", "a/../../b", "C:/x", "a//b"])
def test_upload_rejects_unsafe_paths(client, mirror, path):
    h = {"Authorization": f"Bearer {token()}"}
    r = client.post("/forge/upload", json={"repo_full_name": "acme/secret", "commit": "b" * 40, "manifest": [path],
                                           "files": []}, headers=h)
    assert r.status_code == 422


def test_upload_rejects_bad_commit(client, mirror):
    h = {"Authorization": f"Bearer {token()}"}
    r = client.post("/forge/upload", json={"repo_full_name": "acme/secret", "commit": "../../zzzz", "manifest": [],
                                           "files": []}, headers=h)
    assert r.status_code == 422


@pytest.mark.parametrize("name", ["../etc", "acme/../../x", "acme", "a b/c", "acme/orders;rm -rf"])
def test_clone_url_rejects_unsafe_names(name):
    from specweft import indexer
    with pytest.raises(indexer.IndexError_):
        indexer.clone_url(name)


def test_prewarm_queues_public_repo(client, monkeypatch):
    calls = []
    monkeypatch.setattr(forge.indexer, "request_index", lambda conn, full, db=None: calls.append(full) or {"status": "queued"})
    r = client.post("/forge/prewarm", json={"repo_full_name": "ws/newrepo"}, headers={"Authorization": f"Bearer {token()}"})
    assert r.status_code == 200, r.text
    assert calls == ["ws/newrepo"] and r.json()["job"]["status"] == "queued"


def test_progress_reports_phase_and_elapsed():
    p = forge._progress({"status": "running", "started_at": "2000-01-01T00:00:00+00:00"})
    assert p["phase"] == "Cloning and indexing" and p["elapsed_seconds"] > 0
