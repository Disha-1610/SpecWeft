"""Waze for Code: navigation relationships learned from normalized trajectory events.

Per session (events in `seq` order):
  * first edit           = first `edit` event with a mapped path
  * post-edit navigation = files read/edited (≠A) within WINDOW events after an edit of A
  * detour               = files read/edited after a test_fail/build_fail, before the next test/build run,
                           attributed to every file edited before the failure
Per repository:
  n_A    = sessions that edited A                     base_B = sessions that visited B / sessions
  n_AB   = sessions with edge A→B                     P(B|A) = (n_AB + α·base_B) / (n_A + α), α = 1
  lift   = P(B|A) / base_B
  score  = (1 − e^(−n_AB/2)) · clip(log2(lift)/4, 0, 1) + 0.1·min(n_detour, 3), capped at 1
"""
from __future__ import annotations

import json
import math
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field

from .db import transaction

WINDOW = 15
ALPHA = 1.0


@dataclass
class SessionNav:
    session_id: int
    repo: str
    first_edit: str | None
    visited: set[str]
    edited: set[str]
    edges: dict[tuple[str, str], dict] = field(default_factory=dict)  # (A,B) -> {detour: bool, excerpt, ts}


def load_events(conn: sqlite3.Connection, session_ids: list[int] | None = None) -> dict[int, list[sqlite3.Row]]:
    q = ("SELECT e.session_id, e.seq, e.kind, e.path, e.excerpt, e.ts, s.repo_name FROM events e"
         " JOIN sessions s ON s.id=e.session_id")
    params: list = []
    if session_ids is not None:
        q += f" WHERE e.session_id IN ({','.join('?' * len(session_ids))})"
        params = session_ids
    out: dict[int, list[sqlite3.Row]] = defaultdict(list)
    for r in conn.execute(q + " ORDER BY e.session_id, e.seq", params):
        out[r["session_id"]].append(r)
    return out


def analyze_session(session_id: int, events: list, window: int = WINDOW) -> SessionNav:
    """Sequencing, first edit, post-edit navigation and detours for one session."""
    repo = events[0]["repo_name"] if events else ""
    visited = {e["path"] for e in events if e["path"] and e["kind"] in ("read", "edit")}
    edited_order = [e["path"] for e in events if e["path"] and e["kind"] == "edit"]
    nav = SessionNav(session_id, repo, edited_order[0] if edited_order else None, visited, set(edited_order))
    edited_so_far: list[str] = []
    for i, e in enumerate(events):
        if e["kind"] == "edit" and e["path"]:
            a = e["path"]
            for f in events[i + 1:i + 1 + window]:
                b = f["path"]
                if b and b != a and f["kind"] in ("read", "edit"):
                    nav.edges.setdefault((a, b), {"detour": False, "excerpt": f["excerpt"], "ts": f["ts"]})
            if a not in edited_so_far:
                edited_so_far.append(a)
        elif e["kind"] in ("test_fail", "build_fail") and edited_so_far:
            for f in events[i + 1:]:
                if f["kind"] in ("test_run", "build_run"):
                    break
                b = f["path"]
                if b and f["kind"] in ("read", "edit"):
                    for a in edited_so_far:
                        if a != b:
                            ed = nav.edges.setdefault((a, b), {"detour": False, "excerpt": f["excerpt"], "ts": f["ts"]})
                            if not ed["detour"]:
                                ed["detour"] = True
                                ed["excerpt"] = f"after {e['kind']}: {f['excerpt']}"
    return nav


def nav_score(n_ab: int, n_a: int, base_b: float, n_detour: int) -> tuple[float, float, float]:
    """Returns (P(B|A), lift, score)."""
    base_b = max(base_b, 1e-6)
    p = (n_ab + ALPHA * base_b) / (n_a + ALPHA)
    lift = p / base_b
    score = (1 - math.exp(-n_ab / 2)) * min(1.0, max(0.0, math.log2(lift) / 4)) if lift > 1 else 0.0
    score = min(1.0, score + 0.1 * min(n_detour, 3)) if n_ab > 0 else 0.0
    return p, lift, score


def compute_edges(navs: list[SessionNav]) -> tuple[dict, dict, dict]:
    """Aggregate per repo -> (edges, baseline, sources)."""
    by_repo: dict[str, list[SessionNav]] = defaultdict(list)
    for n in navs:
        by_repo[n.repo or ""].append(n)
    edges: dict[tuple[str, str, str], dict] = {}
    baseline: dict[tuple[str, str], tuple[int, float]] = {}
    sources: dict[tuple[str, str], int] = {}
    for repo, ns in by_repo.items():
        total = len(ns)
        visits: dict[str, int] = defaultdict(int)
        n_src: dict[str, int] = defaultdict(int)
        agg: dict[tuple[str, str], dict] = defaultdict(lambda: {"n": 0, "det": 0, "last": None, "samples": []})
        for n in ns:
            for f in n.visited:
                visits[f] += 1
            for a in n.edited:
                n_src[a] += 1
            for (a, b), info in n.edges.items():
                g = agg[(a, b)]
                g["n"] += 1
                g["det"] += int(info["detour"])
                if info["ts"] and (g["last"] is None or info["ts"] > g["last"]):
                    g["last"] = info["ts"]
                if len(g["samples"]) < 3:
                    g["samples"].append({"session": n.session_id, "excerpt": (info["excerpt"] or "")[:200],
                                         "detour": info["detour"]})
        for f, c in visits.items():
            baseline[(repo, f)] = (c, c / total)
        for a, c in n_src.items():
            sources[(repo, a)] = c
        for (a, b), g in agg.items():
            p, lift, score = nav_score(g["n"], n_src[a], visits[b] / total, g["det"])
            edges[(repo, a, b)] = {"n": g["n"], "det": g["det"], "p": p, "lift": lift, "score": score,
                                   "last": g["last"], "samples": g["samples"]}
    return edges, baseline, sources


def build_navigation(conn: sqlite3.Connection, window: int = WINDOW) -> dict[str, int]:
    evs = load_events(conn)
    navs = [analyze_session(sid, rows, window) for sid, rows in evs.items()]
    edges, baseline, sources = compute_edges(navs)
    with transaction(conn):
        conn.execute("DELETE FROM nav_edges")
        conn.execute("DELETE FROM nav_baseline")
        conn.execute("DELETE FROM nav_sources")
        conn.executemany("INSERT INTO nav_edges VALUES (?,?,?,?,?,?,?,?,?,?)",
                         [(r, a, b, e["n"], e["det"], e["p"], e["lift"], e["score"], e["last"], json.dumps(e["samples"]))
                          for (r, a, b), e in edges.items()])
        conn.executemany("INSERT INTO nav_baseline VALUES (?,?,?,?)",
                         [(r, f, c, rate) for (r, f), (c, rate) in baseline.items()])
        conn.executemany("INSERT INTO nav_sources VALUES (?,?,?)", [(r, a, c) for (r, a), c in sources.items()])
    return {"sessions": len(navs), "edges": len(edges), "files": len(baseline),
            "sessions_with_edit": sum(1 for n in navs if n.first_edit)}


def repo_matches(nav_repo: str | None, repo: str) -> bool:
    """Navigation repos may be `owner/name` while scanned repos are `name`."""
    if not nav_repo:
        return False
    return nav_repo == repo or nav_repo.split("/")[-1] == repo.split("/")[-1]


def neighbors(conn: sqlite3.Connection, repo: str, path: str) -> list[dict]:
    """Outgoing navigation edges for a changed file (any matching repo alias)."""
    rows = conn.execute("SELECT * FROM nav_edges WHERE src=? ORDER BY score DESC", (path,)).fetchall()
    out = []
    for r in rows:
        if not repo_matches(r["repo_name"], repo):
            continue
        n_a = conn.execute("SELECT n_sessions FROM nav_sources WHERE repo_name=? AND path=?", (r["repo_name"], path)).fetchone()
        base = conn.execute("SELECT rate FROM nav_baseline WHERE repo_name=? AND path=?", (r["repo_name"], r["dst"])).fetchone()
        d = dict(r)
        d["n_src"] = n_a[0] if n_a else 0
        d["baseline"] = base[0] if base else 0.0
        d["samples"] = json.loads(r["sample_sessions"] or "[]")
        out.append(d)
    return out
