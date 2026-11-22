"""Evaluation: historical commit replay (agreements vs co-change) and gold-patch evaluation (navigation).

Metrics (per seed, then averaged over all seeds):
  P@5  = |top5 ∩ truth| / 5        R@10 = |top10 ∩ truth| / |truth|
  cross-repo share = fraction of a method's top-5 predictions located in another repository
  coverage = fraction of seeds for which the method produced ≥1 prediction
"""
from __future__ import annotations

import json
import logging
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from statistics import mean

from . import db, gitutil
from .agreements import build_index
from .cochange import CoChange, from_history
from .extract.registry import classify
from .navigation import analyze_any, compute_edges, load_events, repo_matches
from .ranker import FEATURES, file_level_candidates, rank, weighted_score
from .scanner import scan_repo

log = logging.getLogger(__name__)


def metrics(preds: list[tuple[str, str]], truth: set[tuple[str, str]], home_repo: str) -> dict[str, float]:
    top5, top10 = preds[:5], preds[:10]
    return {"p5": len([p for p in top5 if p in truth]) / 5,
            "r10": len([p for p in top10 if p in truth]) / len(truth) if truth else 0.0,
            "xrepo": (sum(1 for r, _ in top5 if r != home_repo) / len(top5)) if top5 else 0.0,
            "covered": 1.0 if preds else 0.0}


def _summ(rows: list[dict[str, float]]) -> dict[str, float]:
    if not rows:
        return {"n": 0}
    return {"n": len(rows), "P@5": round(mean(r["p5"] for r in rows), 4), "R@10": round(mean(r["r10"] for r in rows), 4),
            "cross_repo_share": round(mean(r["xrepo"] for r in rows), 4), "coverage": round(mean(r["covered"] for r in rows), 4)}


def find_pr(repo_root: str | Path, pr_number: int) -> dict | None:
    """Locate the merge/squash commit of a PR; returns {merge, base, files} (base = first parent)."""
    out = gitutil.git(repo_root, "log", "--all", "--format=%H%x1f%s").decode("utf-8", "replace")
    rx = re.compile(rf"(Merge pull request #{pr_number}\b|\(#{pr_number}\)\s*$)")
    for line in out.splitlines():
        sha, _, subj = line.partition("\x1f")
        if rx.search(subj):
            base = gitutil.git(repo_root, "rev-parse", f"{sha}^1").decode().strip()
            files = gitutil.git(repo_root, "diff", "--name-only", base, sha).decode().split()
            return {"merge": sha, "base": base, "files": files}
    return None


# ---------------------------------------------------------------- historical replay (Broken Agreements)

def replay(db_path: str, target_root: str, target_name: str | None = None, other_repos: list[tuple[str, str]] = (),
           cutoff: str | None = None, max_commits: int = 150, seeds_per_commit: int = 3,
           label_conn: sqlite3.Connection | None = None, run: str = "replay") -> dict:
    """Leakage-free replay: index + co-change are built from history up to `cutoff`; later commits are replayed."""
    target_name = target_name or Path(target_root).name
    p = Path(db_path)
    for suffix in ("", "-wal", "-shm"):
        Path(str(p) + suffix).unlink(missing_ok=True)
    conn = db.connect(db_path)
    history = gitutil.commits(target_root, "HEAD")
    if len(history) < 10:
        raise ValueError("not enough history to replay")
    cutoff = cutoff or history[int(len(history) * 0.8)]["sha"]
    cutoff_ts = int(gitutil.git(target_root, "log", "-1", "--format=%ct", cutoff).decode().strip())
    # the target and the explicitly related repos form one workspace group
    scan_repo(conn, target_root, target_name, rev=cutoff, group=target_name)
    for root, name in other_repos:
        rev = gitutil.git(root, "rev-list", "-1", f"--before=@{cutoff_ts}", "HEAD").decode().strip()
        if rev:
            scan_repo(conn, root, name, rev=rev, group=target_name)
    idx = build_index(conn)
    cc = from_history(target_root, cutoff)
    tree = set(gitutil.ls_files(target_root, cutoff))
    later = gitutil.commits(target_root, f"{cutoff}..HEAD")[:max_commits]
    rows: dict[str, list] = defaultdict(list)
    n_labels = 0
    evals: list[dict] = []  # per-seed candidate pools for the fused-LR holdout (fusion_holdout)
    for ci, c in enumerate(later):
        old_names = {v: k for k, v in c["renames"].items()}
        present = sorted({old_names.get(f, f) for f in c["files"]} & tree)
        if len(present) >= 2 and len(present) <= 30:
            seeds = [f for f in present if classify(f, "") is not None][:seeds_per_commit]
            for seed in seeds:
                truth = {(target_name, f) for f in present if f != seed}
                diff = gitutil.git(target_root, "show", "-U3", "-M", "--format=", c["sha"], "--", seed,
                                   *([c["renames"][seed]] if seed in c["renames"] else [])).decode("utf-8", "replace")
                pool = rank(conn, target_name, [seed], diff, limit=200, now=c["ts"], use_model=False, cochange=cc)
                recs = pool[:30]
                fused = [(r.related_file.repo, r.related_file.path) for r in recs]
                # agreement-only ordering must not depend on co-change (ties broken by the co-change-free rule)
                agree_only = [(r.related_file.repo, r.related_file.path) for r in
                              sorted([r for r in pool if r.features["agreement"] > 0], key=lambda r: (-r.features["agreement"], -weighted_score(
                                  {k: v for k, v in r.features.items() if k != "cochange"}), r.related_file.path))]
                co = [(target_name, b) for b, _ in cc.predict(seed, 10)]
                rows["agreement"].append(metrics(agree_only, truth, target_name))
                # same ranking restricted to the home repo: cross-repo predictions are unverifiable against
                # single-repo commit history, so this isolates in-repo precision (reported separately, labelled)
                rows["agreement_in_repo_only"].append(metrics([p for p in agree_only if p[0] == target_name], truth, target_name))
                rows["fused_weighted"].append(metrics(fused, truth, target_name))
                rows["cochange_baseline"].append(metrics(co, truth, target_name))
                evals.append({"commit": ci, "truth": truth, "cochange": co,
                              "cands": [((r.related_file.repo, r.related_file.path), r.features) for r in pool]})
                if label_conn is not None:
                    with label_conn:
                        for r in recs:
                            lab = int((r.related_file.repo, r.related_file.path) in truth)
                            label_conn.execute(
                                "INSERT OR REPLACE INTO replay_labels(run, repo_name, commit_sha, seed, candidate, features, label)"
                                " VALUES (?,?,?,?,?,?,?)", (run, target_name, c["sha"], seed,
                                                            f"{r.related_file.repo}:{r.related_file.path}",
                                                            json.dumps(r.features), lab))
                            n_labels += 1
        cc.add_commit(c["files"])  # online update: the baseline only ever sees the past
    conn.close()
    return {"repo": target_name, "cutoff": cutoff, "index": idx, "commits_replayed": len(later),
            "methods": {k: _summ(v) for k, v in rows.items()}, "labels_written": n_labels,
            "fusion_holdout": _cache_and_holdout(db_path, evals, target_name),
            "note": "truth = other files changed in the same commit that existed at the cutoff; index snapshot at cutoff"}


ABLATIONS = {"lr_agreement+cochange+navigation": ("agreement", "navigation", "cochange", "cross_repo", "detours", "recency"),
             "lr_agreement+navigation (no cochange)": ("agreement", "navigation", "cross_repo", "detours", "recency"),
             "lr_cochange+recency (no agreement)": ("cochange", "recency"),
             "lr_agreement_x_cochange_interaction": ("agreement", "navigation", "cochange", "agreement_x_cochange",
                                                    "both_agree_cochange", "cross_repo", "detours", "recency")}


def _feat(f: dict, k: str) -> float:
    """Raw feature, or a derived combined-candidate feature (agreement and co-change both point at the file)."""
    if k == "agreement_x_cochange":
        return f.get("agreement", 0.0) * f.get("cochange", 0.0)
    if k == "both_agree_cochange":
        return 1.0 if f.get("agreement", 0.0) > 0 and f.get("cochange", 0.0) > 0 else 0.0
    return f.get(k, 0.0)


def _cache_and_holdout(db_path: str, evals: list[dict], home: str) -> dict:
    """Save the per-seed candidate pools next to the replay DB so ablations re-run in seconds (`holdout_from_cache`)."""
    Path(db_path).with_suffix(".pools.json").write_text(json.dumps(
        [{"commit": e["commit"], "truth": sorted(e["truth"]), "cochange": e["cochange"], "cands": e["cands"]}
         for e in evals]), encoding="utf-8")
    return fusion_holdout(evals, home)


def holdout_from_cache(pools_path: str, home: str) -> dict:
    evals = json.loads(Path(pools_path).read_text(encoding="utf-8"))
    for e in evals:
        e["truth"] = {tuple(t) for t in e["truth"]}
        e["cochange"] = [tuple(x) for x in e["cochange"]]
        e["cands"] = [(tuple(k), f) for k, f in e["cands"]]
    return fusion_holdout(evals, home)


def fusion_holdout(evals: list[dict], home: str) -> dict:
    """Temporal split over replayed commits: fit LR on the earlier half's candidate pools, then re-rank the whole
    pool of every later-half seed and score R@10 / P@5 against the full truth set (same metric as `methods`),
    side by side with the co-change baseline on exactly the same seeds."""
    from sklearn.linear_model import LogisticRegression
    commits = sorted({e["commit"] for e in evals})
    if len(commits) < 4:
        return {"evaluated": False, "reason": "too few commits"}
    split = commits[len(commits) // 2]
    tr = [e for e in evals if e["commit"] < split]
    te = [e for e in evals if e["commit"] >= split]
    out: dict = {"evaluated": True, "train_seeds": len(tr), "test_seeds": len(te), "methods": {}, "coef": {}}
    rows: dict[str, list] = defaultdict(list)
    for e in te:
        rows["cochange_baseline"].append(metrics(e["cochange"], e["truth"], home))
        rows["fused_weighted"].append(metrics([k for k, _ in e["cands"]], e["truth"], home))
    for name, feats in ABLATIONS.items():
        X = [[_feat(f, k) for k in feats] for e in tr for _, f in e["cands"]]
        y = [int(key in e["truth"]) for e in tr for key, _ in e["cands"]]
        if len(set(y)) < 2:
            out["methods"][name] = {"n": 0, "reason": "single class in training half"}
            continue
        clf = LogisticRegression(class_weight="balanced", max_iter=2000).fit(X, y)
        out["coef"][name] = {k: round(float(c), 3) for k, c in zip(feats, clf.coef_[0])}
        for e in te:
            if not e["cands"]:
                rows[name].append(metrics([], e["truth"], home))
                continue
            p = clf.predict_proba([[_feat(f, k) for k in feats] for _, f in e["cands"]])[:, 1]
            order = sorted(zip(p, (k for k, _ in e["cands"])), key=lambda x: (-x[0], x[1]))
            rows[name].append(metrics([k for _, k in order], e["truth"], home))
    out["methods"] |= {k: _summ(v) for k, v in rows.items()}
    out["note"] = ("navigation is 0 throughout commit replay (no agent sessions exist for these commits), so its "
                   "LR weight is not learned here; it is fused at inference time via the weighted rule")
    return out


def lr_holdout(label_conn: sqlite3.Connection, run: str) -> dict:
    """Train LR on the earlier half of replay commits, evaluate AUC + P@5 on the later half (temporal split)."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    rows = label_conn.execute("SELECT id, commit_sha, seed, candidate, features, label FROM replay_labels WHERE run=?"
                              " ORDER BY id", (run,)).fetchall()
    commits = list(dict.fromkeys(r[1] for r in rows))
    if len(commits) < 4:
        return {"evaluated": False, "reason": "too few commits"}
    train_c = set(commits[: len(commits) // 2])
    tr = [r for r in rows if r[1] in train_c]
    te = [r for r in rows if r[1] not in train_c]
    X = lambda rs: [[json.loads(r[4]).get(k, 0.0) for k in FEATURES] for r in rs]
    ytr, yte = [r[5] for r in tr], [r[5] for r in te]
    if len(set(ytr)) < 2 or len(set(yte)) < 2:
        return {"evaluated": False, "reason": "a split has a single class"}
    clf = LogisticRegression(class_weight="balanced", max_iter=1000).fit(X(tr), ytr)
    p_lr = clf.predict_proba(X(te))[:, 1]
    p_w = [weighted_score(json.loads(r[4])) for r in te]
    groups: dict[tuple, list] = defaultdict(list)
    for r, a, b in zip(te, p_lr, p_w):
        groups[(r[1], r[2])].append((a, b, r[5]))
    def p_at5(idx: int) -> float:
        vals = []
        for items in groups.values():
            top = sorted(items, key=lambda x: -x[idx])[:5]
            vals.append(sum(x[2] for x in top) / 5)
        return round(mean(vals), 4)
    return {"evaluated": True, "train_labels": len(tr), "test_labels": len(te),
            "auc_lr": round(float(roc_auc_score(yte, p_lr)), 4), "auc_weighted": round(float(roc_auc_score(yte, p_w)), 4),
            "P@5_lr_rerank": p_at5(0), "P@5_weighted_rerank": p_at5(1),
            "coef": {k: round(float(c), 3) for k, c in zip(FEATURES, clf.coef_[0])},
            "note": "P@5 here re-ranks only the candidates the ranker produced (labels table), not all files"}


# ---------------------------------------------------------------- gold-patch evaluation (Waze for Code)

def gold_eval(conn: sqlite3.Connection, nav_repo: str, scanned_repo: str | None = None,
              repo_root: str | None = None, cochange_rev: str = "HEAD", gold_override: list[str] | None = None,
              label_conn: sqlite3.Connection | None = None) -> dict:
    """For each resolved trajectory with a ≥2-file gold patch: seed = first gold file the agent edited;
    predict the rest from navigation learned on OTHER trajectories (leave-one-instance-out when possible)."""
    sess = conn.execute("SELECT id, instance_id, gold_files FROM sessions WHERE gold_files IS NOT NULL").fetchall()
    sess = [s for s in sess if repo_matches(conn.execute("SELECT repo_name FROM sessions WHERE id=?", (s[0],)).fetchone()[0], nav_repo)]
    all_ids = [r[0] for r in conn.execute("SELECT id, repo_name FROM sessions").fetchall()
               if repo_matches(r[1], nav_repo)]
    events = load_events(conn, all_ids) if all_ids else {}
    navs = {sid: analyze_any(sid, events.get(sid, [])) for sid in all_ids}
    inst = {r[0]: r[1] for r in conn.execute("SELECT id, instance_id FROM sessions")}
    files_in_repo: set[str] | None = None
    if scanned_repo:
        files_in_repo = {r[0] for r in conn.execute(
            "SELECT f.path FROM files f JOIN repos r ON r.id=f.repo_id WHERE r.name=?", (scanned_repo,))}
        if repo_root and gitutil.is_repo(repo_root):
            files_in_repo |= set(gitutil.ls_files(repo_root, cochange_rev))
    cc: CoChange | None = from_history(repo_root, cochange_rev) if repo_root else None
    rows: dict[str, list] = defaultdict(list)
    leakage_mode = set()
    details = []
    for sid, instance, gold_json in sess:
        gold = gold_override or json.loads(gold_json)
        if files_in_repo is not None:
            gold = [g for g in gold if g in files_in_repo]  # drop scratch files (reproduce.py etc.)
        if len(gold) < 2:
            continue
        edits = [e["path"] for e in events.get(sid, []) if e["kind"] == "edit" and e["path"] in gold]
        seed = edits[0] if edits else gold[0]
        truth = {(nav_repo, g) for g in gold if g != seed}
        others = [n for i, n in navs.items() if i != sid and inst.get(i) != instance]
        mode = "leave-one-instance-out"
        if not others:
            others = [n for i, n in navs.items() if i != sid]
            mode = "leave-one-trajectory-out (same instance; optimistic)"
        leakage_mode.add(mode)
        edges, _, _ = compute_edges(others)
        nav_preds = sorted(((b, e["score"]) for (r, a, b), e in edges.items() if a == seed and e["score"] > 0),
                           key=lambda x: (-x[1], x[0]))
        det_map = {b: e["det"] for (r, a, b), e in edges.items() if a == seed}
        nav_list = [(nav_repo, b) for b, _ in nav_preds]
        rows["navigation"].append(metrics(nav_list, truth, nav_repo))
        agree_list: list[tuple[str, str]] = []
        if scanned_repo:
            ac = sorted(file_level_candidates(conn, scanned_repo, seed), key=lambda c: -c.score)
            agree_list = [(nav_repo if c.repo == scanned_repo else c.repo, c.path) for c in ac]
            rows["agreement"].append(metrics(agree_list, truth, nav_repo))
            fused_scores: dict[tuple[str, str], float] = defaultdict(float)
            nav_map = dict(nav_preds)
            co_map = {(nav_repo, b): v for b, v in cc.predict(seed, 50)} if cc is not None else {}
            agr_map = {(nav_repo if c.repo == scanned_repo else c.repo, c.path): c.score for c in ac}
            for key in set(agr_map) | {(nav_repo, b) for b in nav_map} | set(co_map):
                f = {"agreement": agr_map.get(key, 0.0), "navigation": nav_map.get(key[1], 0.0) if key[0] == nav_repo else 0.0,
                     "cochange": co_map.get(key, 0.0),
                     "cross_repo": 0.0 if key[0] == nav_repo else 1.0,
                     "detours": min(det_map.get(key[1], 0), 3) / 3, "recency": 0.0}
                fused_scores[key] = weighted_score(f)
            fused = [k for k, _ in sorted(fused_scores.items(), key=lambda x: (-x[1], x[0]))]
            if label_conn is not None:
                with label_conn:
                    for key in fused[:30]:
                        f = {"agreement": agr_map.get(key, 0.0), "navigation": nav_map.get(key[1], 0.0),
                             "cochange": co_map.get(key, 0.0),
                             "cross_repo": 0.0, "detours": min(det_map.get(key[1], 0), 3) / 3, "recency": 0.0}
                        label_conn.execute(
                            "INSERT OR REPLACE INTO replay_labels(run, repo_name, commit_sha, seed, candidate, features, label)"
                            " VALUES (?,?,?,?,?,?,?)", (f"gold:{nav_repo}", nav_repo, f"session-{sid}", seed,
                                                        f"{key[0]}:{key[1]}", json.dumps(f), int(key in truth)))
            rows["fused_weighted"].append(metrics(fused, truth, nav_repo))
        if cc is not None:
            rows["cochange_baseline"].append(metrics([(nav_repo, b) for b, _ in cc.predict(seed, 10)], truth, nav_repo))
        details.append({"session": sid, "seed": seed, "truth": sorted(t[1] for t in truth),
                        "nav_top5": [b for b, _ in nav_preds[:5]], "agreement_top5": [p for _, p in agree_list[:5]]})
    return {"repo": nav_repo, "evaluation_mode": sorted(leakage_mode), "methods": {k: _summ(v) for k, v in rows.items()},
            "gold_definition": "files of the resolved trajectory patch that exist in the repository" if not gold_override
            else "files changed by the upstream PR", "details": details[:10]}
