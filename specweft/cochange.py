"""Git co-change baseline: files that historically changed together."""
from __future__ import annotations

import sqlite3
from collections import defaultdict
from itertools import permutations
from pathlib import Path

from . import gitutil
from .db import transaction

MAX_FILES_PER_COMMIT = 30


class CoChange:
    """In-memory co-change counts; supports online updates during replay (no leakage)."""

    def __init__(self) -> None:
        self.pair: dict[tuple[str, str], int] = defaultdict(int)
        self.single: dict[str, int] = defaultdict(int)

    def add_commit(self, files: list[str]) -> None:
        files = sorted(set(files))
        if not 2 <= len(files) <= MAX_FILES_PER_COMMIT:
            for f in files:
                self.single[f] += 1
            return
        for f in files:
            self.single[f] += 1
        for a, b in permutations(files, 2):
            self.pair[(a, b)] += 1

    def predict(self, seed: str, k: int = 10, exclude: set[str] | None = None) -> list[tuple[str, float]]:
        n_a = self.single.get(seed, 0)
        if not n_a:
            return []
        cands = [(b, n / n_a, n) for (a, b), n in self.pair.items() if a == seed and (not exclude or b not in exclude)]
        cands.sort(key=lambda x: (-x[1], -x[2], x[0]))
        return [(b, conf) for b, conf, _ in cands[:k]]


def from_history(repo_root: str | Path, rev_range: str = "HEAD", max_count: int | None = 5000) -> CoChange:
    cc = CoChange()
    for c in gitutil.commits(repo_root, rev_range, max_count=max_count):
        cc.add_commit(c["files"])
    return cc


def store(conn: sqlite3.Connection, repo_name: str, cc: CoChange) -> int:
    with transaction(conn):
        conn.execute("DELETE FROM cochange WHERE repo_name=?", (repo_name,))
        conn.executemany("INSERT INTO cochange VALUES (?,?,?,?,?)",
                         [(repo_name, a, b, n, cc.single[a]) for (a, b), n in cc.pair.items()])
    return len(cc.pair)


def predict_db(conn: sqlite3.Connection, repo_name: str, seed: str, k: int = 10) -> list[tuple[str, float]]:
    return [(r[0], r[1]) for r in conn.execute(
        "SELECT b, CAST(n AS REAL)/n_a AS conf FROM cochange WHERE repo_name=? AND a=? ORDER BY conf DESC, n DESC, b LIMIT ?",
        (repo_name, seed, k))]
