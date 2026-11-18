import json
import random

from specweft import cochange, evaluation, navigation, ranker
from specweft.models import NormalizedEvent, NormalizedSession
from specweft.traces.ingest import store_session
from tests.conftest import git
from tests.test_scan_index_diff import DIFF_RENAME


def _nav(conn, repo, src, dst, n=3):
    for i in range(n):
        store_session(conn, NormalizedSession("swe_agent", f"{src}-{dst}-{i}", repo,
                                              [NormalizedEvent(0, "edit", src, src), NormalizedEvent(1, "read", dst, dst)]))
    store_session(conn, NormalizedSession("swe_agent", "noise", repo, [NormalizedEvent(0, "read", "README.md", "README.md")]))
    navigation.build_navigation(conn)


def test_rank_fuses_and_dual_signal_is_high_confidence(indexed):
    _nav(indexed, "backend", "app/settings.py", "deploy/k8s.yaml")
    recs = ranker.rank(indexed, "backend", ["app/settings.py"], DIFF_RENAME)
    by = {(r.related_file.repo, r.related_file.path): r for r in recs}
    k8s = by[("backend", "deploy/k8s.yaml")]
    assert k8s.confidence == "high" and k8s.features["agreement"] > 0 and k8s.features["navigation"] > 0
    assert k8s.navigation_evidence.sessions_with_edge == 3 and k8s.agreement_evidence
    single = [r for r in recs if r.features["navigation"] == 0]
    assert single and all(r.confidence in ("medium", "low") for r in single)
    # dual-signal boost: same agreement score ranks above a single-signal candidate
    assert recs[0].related_file.path == "deploy/k8s.yaml"
    fe = by[("frontend", ".env")]
    assert fe.cross_repo and fe.features["cross_repo"] == 1.0
    assert all(r.confidence_basis == "uncalibrated_weighted" for r in recs)
    d = k8s.to_dict()  # shared evidence schema
    assert {"changed_file", "related_file", "reason", "agreement_evidence", "navigation_evidence", "confidence",
            "confidence_score", "ranking_score", "explanation"} <= set(d)


def test_rank_without_diff_uses_file_level_agreements(indexed):
    recs = ranker.rank(indexed, "frontend", ["src/api.ts"])
    assert any(r.related_file.repo == "backend" for r in recs)
    assert all(e.change_type == "touched" for r in recs for e in r.agreement_evidence)


def test_logistic_refuses_without_enough_labels(conn):
    res = ranker.train_logistic(conn)
    assert res["trained"] is False and "need" in res["reason"]
    assert ranker.load_model(conn) is None


def test_logistic_trains_and_respects_observed_features(indexed):
    rnd = random.Random(0)
    with indexed:
        for i in range(120):
            a = rnd.random(); lab = int(a + rnd.random() * 0.3 > 0.7)
            indexed.execute("INSERT INTO replay_labels(run, repo_name, commit_sha, seed, candidate, features, label)"
                            " VALUES ('t','r',?,?,?,?,?)", (f"c{i}", "s", f"x{i}", json.dumps(
                                {"agreement": a, "navigation": 0, "cross_repo": 0, "detours": 0, "recency": rnd.random()}), lab))
    res = ranker.train_logistic(indexed)
    assert res["trained"] and res["params"]["coef"]["agreement"] > 0
    assert "navigation" not in res["params"]["observed_features"]
    recs = ranker.rank(indexed, "backend", ["app/settings.py"], DIFF_RENAME)
    assert any(r.confidence_basis == "logistic_regression" for r in recs)
    _nav(indexed, "backend", "app/settings.py", "deploy/k8s.yaml")
    recs = ranker.rank(indexed, "backend", ["app/settings.py"], DIFF_RENAME)
    k8s = next(r for r in recs if r.related_file.path == "deploy/k8s.yaml")
    assert k8s.confidence_basis == "uncalibrated_weighted"  # navigation unseen by the model -> weighted rule


def test_cochange_counts_and_prediction():
    cc = cochange.CoChange()
    cc.add_commit(["a", "b"]); cc.add_commit(["a", "b", "c"]); cc.add_commit(["a"])
    assert cc.predict("a")[0] == ("b", 2 / 3)
    assert cc.predict("zzz") == []


def test_metrics():
    m = evaluation.metrics([("r", "a"), ("x", "b"), ("r", "c")], {("r", "a"), ("r", "z")}, "r")
    assert m["p5"] == 0.2 and m["r10"] == 0.5 and m["xrepo"] == 1 / 3 and m["covered"] == 1.0
    assert evaluation.metrics([], {("r", "a")}, "r")["covered"] == 0.0


def test_replay_end_to_end_on_fixture_history(tmp_path, repos, conn):
    root = repos["backend"]
    for i in range(12):  # build a history where settings.py and k8s.yaml co-change via PAYMENT_GATEWAY_URL
        (root / f"notes_{i}.md").write_text(f"note `token_{i}_value`\n", encoding="utf-8")
        git(root, "add", "-A"); git(root, "commit", "-q", "-m", f"n{i}")
    s = (root / "app/settings.py").read_text().replace('"PAYMENT_GATEWAY_URL"', '"PAYMENTS_API_BASE_URL"')
    (root / "app/settings.py").write_text(s, encoding="utf-8")
    k = (root / "deploy/k8s.yaml").read_text().replace("PAYMENT_GATEWAY_URL", "PAYMENTS_API_BASE_URL")
    (root / "deploy/k8s.yaml").write_text(k, encoding="utf-8")
    git(root, "add", "-A"); git(root, "commit", "-q", "-m", "rename env var")
    cutoff = git(root, "rev-parse", "HEAD~1").strip()
    res = evaluation.replay(str(tmp_path / "r.db"), str(root), "backend", [(str(repos["frontend"]), "frontend")],
                            cutoff=cutoff, label_conn=conn, run="t")
    assert res["commits_replayed"] == 1
    ag = res["methods"]["agreement"]
    assert ag["n"] == 2 and ag["R@10"] == 1.0  # each file predicts the other via the renamed token
    assert ag["cross_repo_share"] > 0  # frontend/.env also holds the token
    assert res["labels_written"] > 0
    assert conn.execute("SELECT SUM(label) FROM replay_labels WHERE run='t'").fetchone()[0] >= 2


def test_find_pr(repos):
    root = repos["backend"]
    git(root, "commit", "-q", "--allow-empty", "-m", "Fix thing (#42)")
    pr = evaluation.find_pr(root, 42)
    assert pr and pr["base"] == git(root, "rev-parse", "HEAD~1").strip()
    assert evaluation.find_pr(root, 9999) is None


def test_gold_eval_leave_one_out(indexed):
    for i in range(3):
        evs = [NormalizedEvent(0, "edit", "app/models.py", "app/models.py"),
               NormalizedEvent(1, "read", "migrations/001_init.sql", "x")]
        store_session(indexed, NormalizedSession("swe_agent", f"Own__backend-{i}#{i}", "Own/backend", evs,
                                                 gold_files=["app/models.py", "migrations/001_init.sql", "reproduce.py"]))
    for i in range(3):  # control sessions that never visit the migration -> baseline < 1, lift > 1
        store_session(indexed, NormalizedSession("swe_agent", f"Own__backend-c{i}#0", "Own/backend",
                                                 [NormalizedEvent(0, "read", "README.md", "README.md")]))
    res = evaluation.gold_eval(indexed, "Own/backend", "backend", label_conn=indexed)
    nav = res["methods"]["navigation"]
    assert nav["n"] == 3 and nav["R@10"] == 1.0  # reproduce.py dropped: not a repo file
    assert res["evaluation_mode"] == ["leave-one-instance-out"]
    assert "agreement" in res["methods"] and "fused_weighted" in res["methods"]


def test_groups_isolate_unrelated_repos(conn, repos):
    from specweft import agreements, scanner
    from specweft.diffs import analyze_diff
    scanner.scan_repo(conn, repos["backend"], "backend", group="shop")
    scanner.scan_repo(conn, repos["frontend"], "frontend", group="unrelated")
    agreements.build_index(conn)
    cands, _ = analyze_diff(conn, DIFF_RENAME, "backend")
    assert cands and all(c.repo == "backend" for c in cands)


def test_lr_inactive_when_holdout_shows_no_gain(indexed):
    rnd = random.Random(1)
    with indexed:
        for i in range(60):
            a = rnd.random()
            indexed.execute("INSERT INTO replay_labels(run, repo_name, commit_sha, seed, candidate, features, label)"
                            " VALUES ('t','r',?,?,?,?,?)", (f"c{i}", "s", f"x{i}", json.dumps(
                                {"agreement": a, "navigation": 0, "cross_repo": 0, "detours": 0, "recency": 0}), int(a > .5)))
    res = ranker.train_logistic(indexed, holdout={"auc_lr": 0.6, "auc_weighted": 0.7})
    assert res["trained"] and res["metrics"]["active"] is False
    assert ranker.load_model(indexed) is None and ranker.load_model(indexed, require_active=False) is not None
    recs = ranker.rank(indexed, "backend", ["app/settings.py"], DIFF_RENAME)
    assert all(r.confidence_basis == "uncalibrated_weighted" for r in recs)
