"""Bitbucket PR history as a navigation source: commit order -> edges, reviewer comments -> detours."""
import pytest

from specweft import navigation
from specweft.ranker import rank
from specweft.traces import bitbucket_pr
from specweft.traces.ingest import store_session

REPO = "ws/backend"


@pytest.fixture()
def client_factory(indexed, monkeypatch):
    from fastapi.testclient import TestClient

    from specweft import api, forge
    from tests.test_forge import APP_ID, _Client, token
    monkeypatch.setenv("SPECWEFT_FORGE_APP_ID", APP_ID)
    monkeypatch.delenv("SPECWEFT_FORGE_AUTH", raising=False)
    monkeypatch.setattr(forge, "_jwks_client", lambda url: _Client())
    api.app.state.db_path = indexed.execute("PRAGMA database_list").fetchone()[2]
    yield lambda: (TestClient(api.app), {"Authorization": f"Bearer {token()}"})
    del api.app.state.db_path


def pr(i, commits, comments=(), author="{dev}"):
    return {"id": i, "title": f"PR {i}", "created_on": "2026-01-01T00:00:00+00:00", "author": author,
            "commits": [{"hash": f"{i:02d}{k:038d}", "date": f"2026-01-0{k + 1}T10:00:00+00:00", "message": f"c{k}",
                         "files": files} for k, files in enumerate(commits)],
            "comments": [{"created_on": ts, "user": user, "path": path} for ts, user, path in comments]}


def test_parse_orders_commits_and_reviews():
    p = pr(3, [["a.py"], ["b.py"]], comments=[("2026-01-01T12:00:00+00:00", "{rev}", "a.py"),
                                              ("2026-01-01T13:00:00+00:00", "{dev}", None)])
    p["commits"].reverse()  # Bitbucket returns newest first
    s = bitbucket_pr.parse_pr(REPO, p)
    assert s.source == "bitbucket_pr" and s.external_id == "ws/backend#3"
    assert [(e.kind, e.path) for e in s.events] == [
        ("commit", None), ("edit", "a.py"), ("review", "a.py"), ("commit", None), ("edit", "b.py")]  # author reply dropped
    with pytest.raises(ValueError):
        bitbucket_pr.parse_pr(REPO, {"id": 0})


def test_pr_session_edges_are_cross_commit_and_reviews_are_detours(conn):
    s = bitbucket_pr.parse_pr(REPO, pr(1, [["a.py", "x.py"], ["b.py"], ["c.py"]],
                                       comments=[("2026-01-02T12:00:00+00:00", "{rev}", "b.py")]))
    sid = store_session(conn, s)
    nav = navigation.analyze_any(sid, navigation.load_events(conn, [sid])[sid])
    assert ("a.py", "x.py") not in nav.edges            # same commit: co-change, not navigation
    assert set(nav.edges) >= {("a.py", "b.py"), ("x.py", "b.py"), ("a.py", "c.py"), ("b.py", "c.py")}
    assert not nav.edges[("a.py", "b.py")]["detour"]
    assert nav.edges[("a.py", "c.py")]["detour"] and nav.edges[("b.py", "c.py")]["detour"]
    assert "review comment on b.py" in nav.edges[("b.py", "c.py")]["excerpt"]


def test_endpoint_stores_history_and_navigation_reaches_ranker(conn, client_factory):
    client, hdr = client_factory()
    # 4 PRs where settings.py is followed by k8s.yaml, 2 unrelated PRs (k8s.yaml has a real baseline below 1)
    prs = [pr(i, [["app/settings.py"], ["deploy/k8s.yaml"]]) for i in range(1, 5)]
    prs += [pr(i, [["README.md"], ["app/models.py"]]) for i in range(5, 7)]
    prs.append(pr(7, [["only_one_commit.py"]]))
    r = client.post("/forge/pr-history", json={"repo_full_name": REPO, "pull_requests": prs}, headers=hdr)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["stored"] == 7 and j["pr_sessions"] == 7 and j["edges"] > 0
    # idempotent: re-sending replaces, never duplicates
    j2 = client.post("/forge/pr-history", json={"repo_full_name": REPO, "pull_requests": prs}, headers=hdr).json()
    assert j2["pr_sessions"] == 7
    e = navigation.neighbors(conn, "backend", "app/settings.py")
    assert e and e[0]["dst"] == "deploy/k8s.yaml" and e[0]["n_sessions"] == 4 and e[0]["score"] > 0
    recs = {x.related_file.path: x for x in rank(conn, "backend", ["app/settings.py"])}
    k8s = recs["deploy/k8s.yaml"]
    assert k8s.features["navigation"] > 0 and k8s.features["agreement"] > 0
    assert k8s.confidence == "high"                      # two signals: the merge check can now fire


def test_endpoint_rejects_bad_repo_name(client_factory):
    client, hdr = client_factory()
    r = client.post("/forge/pr-history", json={"repo_full_name": "../etc", "pull_requests": []}, headers=hdr)
    assert r.status_code == 422


def test_repo_scoped_rebuild_keeps_other_repos(conn):
    from specweft.models import NormalizedEvent, NormalizedSession
    for i in range(2):
        store_session(conn, NormalizedSession("swe_agent", f"o{i}", "other",
                                              [NormalizedEvent(0, "edit", "a.py", "a.py"),
                                               NormalizedEvent(1, "read", "b.py", "b.py")]))
    store_session(conn, NormalizedSession("swe_agent", "o9", "other", [NormalizedEvent(0, "read", "z.py", "z.py")]))
    navigation.build_navigation(conn)
    before = conn.execute("SELECT COUNT(*) FROM nav_edges WHERE repo_name='other'").fetchone()[0]
    store_session(conn, bitbucket_pr.parse_pr(REPO, pr(1, [["a.py"], ["b.py"]])))
    navigation.build_navigation(conn, repo=REPO)
    assert conn.execute("SELECT COUNT(*) FROM nav_edges WHERE repo_name='other'").fetchone()[0] == before > 0
    assert conn.execute("SELECT COUNT(*) FROM nav_edges WHERE repo_name=?", (REPO,)).fetchone()[0] == 1
