import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from specweft import api, hook
from tests.helpers import claude_transcript
from tests.test_scan_index_diff import DIFF_RENAME

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture()
def client(indexed, tmp_path):
    db_path = indexed.execute("PRAGMA database_list").fetchone()[2]
    api.app.state.db_path = db_path
    yield TestClient(api.app)
    del api.app.state.db_path


def test_health_and_repos(client):
    h = client.get("/api/health").json()
    assert h["repos"] == 2 and h["agreement_tokens"] > 0
    assert {r["name"] for r in client.get("/api/repos").json()} == {"backend", "frontend"}
    assert client.get("/").status_code == 200


def test_analyze_diff_returns_shared_evidence(client):
    r = client.post("/api/analyze", json={"repo": "backend", "diff": DIFF_RENAME})
    assert r.status_code == 200
    j = r.json()
    assert j["changed_files"] == ["app/settings.py"]
    assert any(t["change_type"] == "renamed" for t in j["token_changes"])
    rec = next(x for x in j["recommendations"] if x["related_file"]["path"] == "deploy/k8s.yaml")
    ev = rec["agreement_evidence"][0]
    assert ev["changed_site"]["line"] == 2 and ev["holder_site"]["line"]


def test_analyze_commit_and_validation(client):
    assert client.post("/api/analyze", json={"repo": "backend", "commit": "HEAD"}).status_code == 200
    assert client.post("/api/analyze", json={"repo": "backend"}).status_code == 422
    assert client.post("/api/analyze", json={"repo": "backend", "diff": "x", "commit": "HEAD"}).status_code == 422
    assert client.post("/api/analyze", json={"repo": "nope", "diff": DIFF_RENAME}).status_code == 422
    assert client.post("/api/analyze", json={"repo": "backend", "diff": "not a diff"}).status_code == 422
    assert client.post("/api/analyze", json={"repo": "backend", "commit": "deadbeef"}).status_code == 422
    assert client.post("/api/analyze", json={"repo": "backend", "commit": "HEAD; rm -rf /"}).status_code == 422


def test_rank_and_holders(client):
    r = client.post("/api/rank", json={"repo": "frontend", "changed_files": ["src/api.ts"]})
    assert r.status_code == 200 and r.json()["recommendations"]
    assert client.post("/api/rank", json={"repo": "frontend", "changed_files": []}).status_code == 422
    h = client.get("/api/agreements/holders", params={"token": "PaymentGatewayUrl"}).json()
    assert h["token"] == "payment_gateway_url" and len(h["holders"]) >= 8


def _hook_payload(tmp_path, repos, edit_rel="app/settings.py", active=False):
    root = repos["backend"]
    (root / edit_rel).write_text((root / edit_rel).read_text().replace('"PAYMENT_GATEWAY_URL"', '"PAYMENTS_API_BASE_URL"'),
                                 encoding="utf-8")
    t = claude_transcript(tmp_path / "t.jsonl", str(root), [
        ("Read", {"file_path": str(root / edit_rel)}, "x", False),
        ("Edit", {"file_path": str(root / edit_rel), "old_string": "a", "new_string": "b"}, "ok", False)])
    return {"session_id": "s", "transcript_path": str(t), "cwd": str(root), "hook_event_name": "Stop",
            "stop_hook_active": active}


def test_hook_run_blocks_once_with_evidence(indexed, tmp_path, repos, monkeypatch):
    from tests.test_ranker_eval import _nav
    _nav(indexed, "backend", "app/settings.py", "deploy/k8s.yaml")
    db_path = indexed.execute("PRAGMA database_list").fetchone()[2]
    res = hook.run(_hook_payload(tmp_path, repos), db_path)
    assert res["status"] == "ok" and res["edited"] == ["app/settings.py"]
    assert res["output"]["decision"] == "block" and "deploy/k8s.yaml" in res["output"]["reason"]
    # second stop in the same turn: never block again
    res2 = hook.run(_hook_payload(tmp_path, repos, active=True), db_path)
    assert "decision" not in res2["output"] and "systemMessage" in res2["output"]
    monkeypatch.setenv("SPECWEFT_HOOK_MODE", "warn")
    assert "decision" not in hook.run(_hook_payload(tmp_path, repos), db_path)["output"]


def test_hook_safe_on_missing_data(indexed, tmp_path):
    db_path = indexed.execute("PRAGMA database_list").fetchone()[2]
    assert hook.run({}, db_path)["status"] == "no_transcript"
    t = tmp_path / "t.jsonl"; t.write_text("", encoding="utf-8")
    assert hook.run({"transcript_path": str(t), "cwd": str(tmp_path)}, db_path)["status"] == "repo_not_indexed"


@pytest.mark.parametrize("stdin", ["", "not json", "[1,2]", json.dumps({"transcript_path": "/nope"})])
def test_hook_process_never_fails(stdin, tmp_path):
    env = dict(os.environ, SPECWEFT_DB=str(tmp_path / "h.db"), SPECWEFT_HOOK_LOG=str(tmp_path / "log.jsonl"))
    p = subprocess.run([sys.executable, "-m", "specweft.hook"], input=stdin, capture_output=True, text=True,
                       cwd=ROOT, env=env, timeout=120)
    assert p.returncode == 0 and p.stdout == ""
    assert (tmp_path / "log.jsonl").read_text().strip()


def test_hook_process_end_to_end(indexed, tmp_path, repos):
    from tests.test_ranker_eval import _nav
    _nav(indexed, "backend", "app/settings.py", "deploy/k8s.yaml")
    db_path = indexed.execute("PRAGMA database_list").fetchone()[2]
    indexed.commit()
    env = dict(os.environ, SPECWEFT_DB=db_path, SPECWEFT_HOOK_LOG=str(tmp_path / "log.jsonl"))
    p = subprocess.run([sys.executable, "-m", "specweft.hook"], input=json.dumps(_hook_payload(tmp_path, repos)),
                       capture_output=True, text=True, cwd=ROOT, env=env, timeout=120)
    assert p.returncode == 0, p.stderr
    out = json.loads(p.stdout)
    assert out["decision"] == "block" and "k8s.yaml" in out["reason"]
