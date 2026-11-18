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


def test_unknown_repo_and_repo_map(client, monkeypatch):
    h = {"Authorization": f"Bearer {token()}"}
    assert client.post("/forge/analyze-pr", json=BODY | {"repo_slug": "nope", "repo_full_name": "ws/nope"},
                       headers=h).status_code == 404
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
    r = client.post("/forge/merge-check", json=BODY | {"repo_slug": "nope", "repo_full_name": "x/nope"}, headers=h).json()
    assert r["success"] is True and "not indexed" in r["message"]


def test_misconfigured_server_fails_closed(client, monkeypatch):
    monkeypatch.delenv("SPECWEFT_FORGE_APP_ID")
    r = client.post("/forge/analyze-pr", json=BODY, headers={"Authorization": f"Bearer {token()}"})
    assert r.status_code == 500
