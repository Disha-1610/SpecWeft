"""Unified ranker: fuses agreement and navigation evidence into ranked, explained recommendations.

Features (all in [0,1]):
  agreement   noisy-or of weighted token scores linking changed -> related file (diffs.analyze_diff)
  navigation  navigation edge score changed -> related (navigation.nav_score)
  cross_repo  1 if related file lives in another repository
  detours     min(n_detour, 3) / 3
  recency     exp(-age_days / 180) of the most recent evidence (nav edge timestamp or holder's last commit)
Fusion:
  weighted (default):  s = 0.55·agreement + 0.35·navigation + 0.05·recency + 0.05·detours   (cross_repo: 0)
                       ×1.25 (capped at 1) when both agreement > 0 and navigation > 0
  logistic regression: used when a model trained on replay labels exists (`train_logistic`) AND every non-zero
                       feature of the candidate varied in the training data (otherwise the model never learned
                       a weight for it, e.g. navigation in commit replay) — then the weighted rule is used.
Confidence: high = both signals; medium = one signal ≥ 0.5, or the file still holds a token this change removed,
renamed or changed the value of (a definite break); low otherwise. `confidence_score` is the LR
probability when a model is used, else the weighted score (marked `uncalibrated_weighted`).
"""
from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from functools import lru_cache

from . import gitutil
from .agreements import repo_group, token_scores
from .diffs import CHANGE_WEIGHTS, AgreementCandidate, analyze_diff
from .models import AgreementEvidence, Location, NavigationEvidence, Recommendation
from .navigation import neighbors

FEATURES = ("agreement", "navigation", "cross_repo", "detours", "recency")
# cross_repo is neutral in the weighted rule: replay gave no evidence that it helps (the trained LR learns a negative
# weight). It remains a feature for the LR and a flag shown to users.
WEIGHTS = {"agreement": 0.55, "navigation": 0.35, "cross_repo": 0.0, "recency": 0.05, "detours": 0.05}
DUAL_BOOST = 1.25
MIN_LR_SAMPLES = 40


def weighted_score(f: dict[str, float]) -> float:
    s = sum(WEIGHTS[k] * f.get(k, 0.0) for k in WEIGHTS)
    if f.get("agreement", 0) > 0 and f.get("navigation", 0) > 0:
        s *= DUAL_BOOST
    return min(1.0, s)


def load_model(conn: sqlite3.Connection, name: str = "fusion_lr", require_active: bool = True) -> dict | None:
    """The trained model, or None. A model is only *active* if held-out evaluation showed it beats the weighted rule."""
    r = conn.execute("SELECT params, n_samples, metrics FROM models WHERE name=?", (name,)).fetchone()
    if not r:
        return None
    m = {"params": json.loads(r[0]), "n_samples": r[1], "metrics": json.loads(r[2] or "{}")}
    if require_active and not m["metrics"].get("active", False):
        return None
    return m


def lr_prob(model: dict, f: dict[str, float]) -> float:
    p = model["params"]
    z = p["intercept"] + sum(p["coef"][k] * f.get(k, 0.0) for k in FEATURES)
    return 1 / (1 + math.exp(-z))


def train_logistic(conn: sqlite3.Connection, run: str | None = None, name: str = "fusion_lr",
                   holdout: dict | None = None) -> dict:
    """Fit LR on replay labels. Refuses (returns reason) when data is insufficient — never fabricates a model."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    q = "SELECT features, label FROM replay_labels" + (" WHERE run=?" if run else "")
    rows = conn.execute(q, (run,) if run else ()).fetchall()
    X = [[json.loads(r[0]).get(k, 0.0) for k in FEATURES] for r in rows]
    y = [int(r[1]) for r in rows]
    if len(y) < MIN_LR_SAMPLES or len(set(y)) < 2:
        return {"trained": False, "reason": f"need ≥{MIN_LR_SAMPLES} labels with both classes, have {len(y)} "
                                            f"({sum(y)} positive)"}
    clf = LogisticRegression(class_weight="balanced", max_iter=1000)
    clf.fit(X, y)
    probs = clf.predict_proba(X)[:, 1]
    metrics = {"train_auc": float(roc_auc_score(y, probs)), "n_pos": int(sum(y)), "n": len(y),
               "note": "in-sample AUC; activation decided by held-out comparison"}
    # Activate only with held-out evidence that LR beats the weighted rule (temporal split, see evaluation.lr_holdout)
    if holdout is not None:
        metrics["holdout"] = holdout
        metrics["active"] = bool(holdout.get("auc_lr", 0) > holdout.get("auc_weighted", 1))
    else:
        metrics["active"] = True  # explicit training without holdout evidence (e.g. tests / CLI `train`)
    observed = [k for i, k in enumerate(FEATURES) if len({row[i] for row in X}) > 1]
    params = {"intercept": float(clf.intercept_[0]), "coef": {k: float(c) for k, c in zip(FEATURES, clf.coef_[0])},
              "observed_features": observed}
    with conn:
        conn.execute("INSERT OR REPLACE INTO models VALUES (?,?,?,?,?)",
                     (name, json.dumps(params), datetime.now(timezone.utc).isoformat(timespec="seconds"), len(y),
                      json.dumps(metrics)))
    return {"trained": True, "params": params, "metrics": metrics}


@lru_cache(maxsize=4096)
def _last_commit_ts(root: str, path: str, before: int | None) -> int | None:
    try:
        args = ["log", "-1", "--format=%ct"] + ([f"--before=@{before - 1}"] if before else []) + ["--", path]
        out = gitutil.git(root, *args).decode().strip()
        return int(out) if out else None
    except (gitutil.GitError, ValueError):
        return None


@lru_cache(maxsize=64)
def _is_repo(root: str) -> bool:
    return gitutil.is_repo(root)


def _recency(ts: int | None, now: int) -> float:
    if not ts:
        return 0.0
    return math.exp(-max(0, now - ts) / 86400 / 180)


def _iso_to_epoch(s: str | None) -> int | None:
    if not s:
        return None
    try:
        return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())
    except ValueError:
        return None


def file_level_candidates(conn: sqlite3.Connection, repo: str, path: str, top_tokens: int = 3,
                          max_holders: int = 60) -> list[AgreementCandidate]:
    """Agreement candidates when no diff is available: every agreement the changed file holds is 'touched'."""
    rows = conn.execute(
        "SELECT o.token_norm, o.token_raw, o.line, o.context FROM occurrences o JOIN files f ON f.id=o.file_id"
        " JOIN repos r ON r.id=f.repo_id WHERE r.name=? AND f.path=?", (repo, path)).fetchall()
    first: dict[str, sqlite3.Row] = {}
    for r in rows:
        first.setdefault(r[0], r)
    scores = token_scores(conn, list(first))
    group = repo_group(conn, repo)
    per_file: dict[tuple[str, str], list[tuple[float, AgreementEvidence]]] = defaultdict(list)
    for tn, s in scores.items():
        src = first[tn]
        for h in conn.execute(
                "SELECT r.name, f.path, o.line, o.context, o.token_raw FROM occurrences o JOIN files f ON f.id=o.file_id"
                " JOIN repos r ON r.id=f.repo_id WHERE o.token_norm=? AND (? IS NULL OR r.group_name=?) LIMIT ?",
                (tn, group, group, max_holders)):
            if (h[0], h[1]) == (repo, path):
                continue
            ev = AgreementEvidence(tn, "touched", round(s, 4), Location(repo, path, src[2], src[3] or src[1]),
                                   Location(h[0], h[1], h[2], h[3] or h[4]))
            per_file[(h[0], h[1])].append((s * CHANGE_WEIGHTS["touched"], ev))
    out = []
    for (hr, hp), items in per_file.items():
        best: dict[str, tuple[float, AgreementEvidence]] = {}
        for w, ev in items:
            if ev.token not in best or w > best[ev.token][0]:
                best[ev.token] = (w, ev)
        top = sorted(best.values(), key=lambda x: -x[0])[:top_tokens]
        prod = 1.0
        for w, _ in top:
            prod *= 1 - w
        out.append(AgreementCandidate(repo, path, hr, hp, 1 - prod, [ev for _, ev in top]))
    return out


def rank(conn: sqlite3.Connection, repo: str, changed_files: list[str], diff_text: str | None = None,
         limit: int = 20, now: int | None = None, nav_conn: sqlite3.Connection | None = None,
         use_model: bool = True) -> list[Recommendation]:
    """Rank files likely affected by changes to `changed_files` (repo-relative) in `repo`."""
    now = now or int(datetime.now(timezone.utc).timestamp())
    nav_conn = nav_conn or conn
    changed = set(changed_files)
    agree: dict[tuple[str, str, str], AgreementCandidate] = {}
    diff_paths: set[str] = set()
    if diff_text:
        cands, _ = analyze_diff(conn, diff_text, repo)
        for c in cands:
            agree[(c.changed_path, c.repo, c.path)] = c
            diff_paths.add(c.changed_path)
    for f in changed_files:
        if f in diff_paths:
            continue
        for c in file_level_candidates(conn, repo, f):
            agree[(f, c.repo, c.path)] = c
    nav: dict[tuple[str, str, str], dict] = {}
    for f in changed_files:
        for e in neighbors(nav_conn, repo, f):
            nav[(f, repo, e["dst"])] = e

    root_row = conn.execute("SELECT root FROM repos WHERE name=?", (repo,)).fetchone()
    model = load_model(conn) if use_model else None
    best: dict[tuple[str, str], tuple[float, Recommendation]] = {}
    for key in set(agree) | set(nav):
        cf, rr, rp = key
        if rr == repo and rp in changed:
            continue
        a = agree.get(key)
        e = nav.get(key)
        f = {"agreement": a.score if a else 0.0, "navigation": e["score"] if e else 0.0,
             "cross_repo": 1.0 if rr != repo else 0.0, "detours": min(e["n_detour"], 3) / 3 if e else 0.0}
        ts = _iso_to_epoch(e["last_ts"]) if e else None
        if ts is None:
            rroot = conn.execute("SELECT root FROM repos WHERE name=?", (rr,)).fetchone()
            root = rroot[0] if rroot else (root_row[0] if root_row else None)
            ts = _last_commit_ts(root, rp, now) if root and _is_repo(root) else None
        f["recency"] = _recency(ts, now)
        w = weighted_score(f)
        if model and all(f[k] == 0 for k in FEATURES if k not in model["params"].get("observed_features", FEATURES)):
            score, conf_score, basis = lr_prob(model, f), lr_prob(model, f), "logistic_regression"
        else:
            score, conf_score, basis = w, w, "uncalibrated_weighted"
        hard_break = bool(a and any(ev.change_type in ("removed", "renamed", "value_changed") for ev in a.evidence))
        if f["agreement"] > 0 and f["navigation"] > 0:
            level = "high"
        elif max(f["agreement"], f["navigation"]) >= 0.5 or hard_break:
            level = "medium"
        else:
            level = "low"
        nev = None
        if e:
            nev = NavigationEvidence(e["n_sessions"], e["n_src"], round(e["baseline"], 4), round(e["lift"], 3),
                                     e["n_detour"], [s["excerpt"] for s in e["samples"]])
        rec = Recommendation(
            changed_file=Location(repo, cf), related_file=Location(rr, rp,
                                                                   a.evidence[0].holder_site.line if a and a.evidence else None),
            reason=_reason(a, e), agreement_evidence=a.evidence if a else [], navigation_evidence=nev,
            cross_repo=rr != repo, features={k: round(v, 4) for k, v in f.items()}, ranking_score=round(score, 4),
            confidence=level, confidence_score=round(conf_score, 4), confidence_basis=basis,
            explanation=_explain(cf, rp, rr, repo, a, e, f, level, basis))
        k2 = (rr, rp)
        if k2 not in best or rec.ranking_score > best[k2][0]:
            best[k2] = (rec.ranking_score, rec)
    recs = [r for _, r in sorted(best.values(), key=lambda x: (-x[0], x[1].related_file.path))]
    return recs[:limit]


def _reason(a: AgreementCandidate | None, e: dict | None) -> str:
    parts = []
    if a and a.evidence:
        ev = a.evidence[0]
        verb = {"removed": "removes", "renamed": "renames", "value_changed": "changes the value of",
                "touched": "touches"}[ev.change_type]
        parts.append(f"change {verb} `{ev.token}` which is still held here")
    if e:
        parts.append(f"{e['n_sessions']}/{e['n_src']} sessions navigated here after editing the changed file"
                     + (f" ({e['n_detour']} after a failing test/build)" if e["n_detour"] else ""))
    return "; ".join(parts) or "no evidence"


def _explain(cf: str, rp: str, rr: str, repo: str, a, e, f, level, basis) -> str:
    s = [f"{rp}{' in ' + rr if rr != repo else ''} may need updating after changes to {cf}."]
    if a and a.evidence:
        toks = ", ".join(f"`{ev.token}` ({ev.change_type}, score {ev.token_score:.2f})" for ev in a.evidence[:3])
        s.append(f"Agreement {f['agreement']:.2f}: shared tokens {toks}.")
    if e:
        s.append(f"Navigation {f['navigation']:.2f}: lift {e['lift']:.1f}× over the {e['baseline']:.0%} baseline visit rate.")
    s.append({"high": "Both systems agree (dual-signal).", "medium": "Single system: strong signal or a definite contract break.",
              "low": "Single weak signal."}[level])
    if basis == "uncalibrated_weighted":
        s.append("Score is an uncalibrated weighted sum (no trained model).")
    return " ".join(s)
