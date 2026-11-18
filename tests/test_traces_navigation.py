import json
from pathlib import Path

import pytest

from specweft import navigation
from specweft.models import NormalizedEvent
from specweft.traces import claude_code, openhands, swe_agent
from specweft.traces.classify import command_kind, output_failed
from specweft.traces.ingest import ingest_file, resolve_paths, store_session
from specweft.traces.paths import canon, map_to_head, rename_map, to_repo_relative
from tests.conftest import git
from tests.helpers import claude_transcript, openhands_row, swe_agent_row

PATCH = "diff --git a/app/models.py b/app/models.py\n--- a/app/models.py\n+++ b/app/models.py\n@@ -1 +1 @@\n-a\n+b\n" \
        "diff --git a/migrations/001_init.sql b/migrations/001_init.sql\n--- a/m\n+++ b/m\n@@ -1 +1 @@\n-a\n+b\n"


def test_command_classification():
    assert command_kind("python -m pytest tests -q") == "test_run"
    assert command_kind("cd app && npm run build") == "build_run"
    assert command_kind("cat app/x.py | head") == "read"
    assert command_kind("grep -rn foo .") == "search"
    assert command_kind("sed -i 's/a/b/' x.py") == "edit"
    assert command_kind("echo hi") is None
    assert output_failed("== 3 passed in 0.1s ==") is False
    assert output_failed("FAILED tests/test_x.py::t - AssertionError") is True
    assert output_failed("", exit_code=1) is True


def test_event_schema_rejects_unknown_kind():
    with pytest.raises(ValueError):
        NormalizedEvent(0, "teleport")


def test_path_mapping():
    assert canon(r"C:\Users\me\repo\a.py") == "C:/Users/me/repo/a.py"
    assert canon("/c/Users/me/repo/a.py") == "C:/Users/me/repo/a.py"
    assert to_repo_relative(r"C:\Users\me\repo\app\x.py", "C:/Users/me/repo") == "app/x.py"
    assert to_repo_relative("app/x.py", "C:/Users/me/repo", "C:/Users/me/repo") == "app/x.py"
    assert to_repo_relative("../app/x.py", "/w/repo", "/w/repo/sub") == "app/x.py"
    assert to_repo_relative("/etc/passwd", "/w/repo") is None
    assert to_repo_relative("/lexicon/lexicon/cli.py", "/lexicon") == "lexicon/cli.py"


def test_commit_aware_mapping(repos):
    root = repos["backend"]
    old = git(root, "rev-parse", "HEAD").strip()
    git(root, "mv", "app/models.py", "app/order_models.py")
    git(root, "commit", "-q", "-m", "rename")
    assert rename_map(str(root), old)["app/models.py"] == "app/order_models.py"
    assert map_to_head("app/models.py", str(root), old) == "app/order_models.py"
    assert map_to_head("app/routes.py", str(root), old) == "app/routes.py"


def test_claude_code_adapter(tmp_path, repos):
    root = repos["backend"]
    t = claude_transcript(tmp_path / "s.jsonl", str(root), [
        ("Read", {"file_path": str(root / "app/settings.py")}, "content", False),
        ("Edit", {"file_path": str(root / "app/settings.py"), "old_string": "a", "new_string": "b"}, "ok", False),
        ("Bash", {"command": "python -m pytest -q"}, "Exit code 1\n1 failed, 2 passed", True),
        ("Read", {"file_path": str(root / "deploy/k8s.yaml")}, "content", False),
        ("Grep", {"pattern": "PAYMENT"}, "x", False),
        ("Bash", {"command": f"cat {root.as_posix()}/.env"}, "x", False),
        ("Write", {"file_path": "/outside/repo.txt", "content": ""}, "ok", False),
    ])
    s = claude_code.parse_session(t)
    assert [e.kind for e in s.events] == ["read", "edit", "test_run", "test_fail", "read", "search", "read", "edit"]
    s = resolve_paths(s)
    assert [e.path for e in s.events if e.kind in ("read", "edit")] == ["app/settings.py", "app/settings.py",
                                                                        "deploy/k8s.yaml", ".env", None]
    assert s.repo_name == "backend" and s.commit_sha  # commit-aware: commit at session time


def test_swe_agent_adapter():
    row = swe_agent_row("Owner__proj-7", [
        ("open app/models.py", "[file]\n(Open file: /proj/app/models.py)\n(Current directory: /proj)\nbash-$"),
        ("edit 1:1\nx\nend_of_edit", "ok\n(Open file: /proj/app/models.py)\n(Current directory: /proj)"),
        ("python -m pytest tests", "FAILED tests/t.py\n(Open file: /proj/app/models.py)\n(Current directory: /proj)"),
        ("open migrations/001_init.sql", "(Open file: /proj/migrations/001_init.sql)\n(Current directory: /proj)"),
        ("search_dir customer_orders", "Found\n(Open file: n/a)\n(Current directory: /proj)"),
        ("submit", "")], patch=PATCH)
    s = resolve_paths(swe_agent.parse_row(row))
    assert s.repo_name == "Owner/proj"
    assert [(e.kind, e.path) for e in s.events] == [("read", "app/models.py"), ("edit", "app/models.py"),
                                                    ("test_run", None), ("test_fail", None),
                                                    ("read", "migrations/001_init.sql"), ("search", None)]
    assert s.gold_files == ["app/models.py", "migrations/001_init.sql"]
    assert swe_agent.parse_row(dict(row, target=False)).gold_files is None


def test_openhands_adapter():
    row = openhands_row("Owner/proj", [
        ("str_replace_editor", {"command": "view", "path": "/workspace/proj"}, "Here's the files and directories up to 2 levels"),
        ("str_replace_editor", {"command": "view", "path": "/workspace/proj/app/models.py"}, "code"),
        ("str_replace_editor", {"command": "str_replace", "path": "/workspace/proj/app/models.py"}, "edited"),
        ("execute_bash", {"command": "cd /workspace/proj && python -m pytest"},
         "1 failed\n[Current working directory: /workspace/proj]\n[Command finished with exit code 1]"),
        ("str_replace_editor", {"command": "view", "path": "/workspace/proj/migrations/001_init.sql"}, "sql"),
    ], patch=PATCH)
    s = resolve_paths(openhands.parse_row(row))
    assert [(e.kind, e.path) for e in s.events] == [("search", None), ("read", "app/models.py"), ("edit", "app/models.py"),
                                                    ("test_run", None), ("test_fail", None),
                                                    ("read", "migrations/001_init.sql")]


def test_ingest_idempotent_and_skips_malformed(conn, tmp_path):
    rows = [swe_agent_row("O__p-1", [("open a.py", "(Open file: /p/a.py)\n(Current directory: /p)")]),
            {"instance_id": "O__p-2", "trajectory": "not-a-list"}]
    f = tmp_path / "rows.json"
    f.write_text(json.dumps({"rows": [{"row": r} for r in rows]}), encoding="utf-8")
    a = ingest_file(conn, "swe_agent", f)
    b = ingest_file(conn, "swe_agent", f)
    assert a["sessions"] + a["skipped"] == 2 and b == a
    assert conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == a["sessions"]
    with pytest.raises(ValueError):
        ingest_file(conn, "nope", f)


def _store(conn, sid, repo, seq):
    from specweft.models import NormalizedSession
    evs = [NormalizedEvent(i, k, p, p) for i, (k, p) in enumerate(seq)]
    store_session(conn, NormalizedSession("swe_agent", sid, repo, evs))


def test_navigation_edges_lift_and_detours(conn):
    # 3 sessions edit A then visit B (one after a failing test); 1 session visits only C.
    for i in range(3):
        seq = [("edit", "a.py"), ("read", "b.py")] if i < 2 else [("edit", "a.py"), ("test_run", None), ("test_fail", None), ("read", "b.py")]
        _store(conn, f"s{i}", "r", seq)
    _store(conn, "s3", "r", [("read", "c.py")])
    stats = navigation.build_navigation(conn)
    assert stats["sessions"] == 4 and stats["sessions_with_edit"] == 3
    e = dict(conn.execute("SELECT * FROM nav_edges WHERE src='a.py' AND dst='b.py'").fetchone())
    assert e["n_sessions"] == 3 and e["n_detour"] == 1
    base_b = 3 / 4
    p = (3 + base_b) / (3 + 1)
    assert e["p_cond"] == pytest.approx(p) and e["lift"] == pytest.approx(p / base_b)
    assert 0 < e["score"] <= 1
    nb = navigation.neighbors(conn, "owner/r", "a.py")  # repo alias owner/name -> name
    assert nb and nb[0]["dst"] == "b.py" and nb[0]["n_src"] == 3


def test_nav_score_properties():
    assert navigation.nav_score(0, 5, 0.1, 0)[2] == 0
    hi = navigation.nav_score(5, 5, 0.1, 0)[2]
    lo = navigation.nav_score(1, 5, 0.1, 0)[2]
    common = navigation.nav_score(5, 5, 0.95, 0)[2]
    assert hi > lo and hi > common


def test_command_paths_reject_inline_code_and_modules():
    from specweft.traces.classify import command_paths
    assert command_paths("cat app/models.py") == ["app/models.py"]
    assert command_paths("head -n 5 C:/x/y/.env") == ["C:/x/y/.env"]
    assert command_paths("cat 'all(c.repo' specweft.diffs foo.bar") == []
    assert command_paths("sed -n 10,20p src/a.ts") == ["src/a.ts"]
