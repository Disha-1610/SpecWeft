"""Agreement index: score tokens shared by ≥2 files and look up their holders."""
from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass

from .db import transaction
from .tokens import NormToken, rarity, specificity, spread


@dataclass(frozen=True)
class Holder:
    repo: str
    path: str
    line: int
    token_norm: str
    token_raw: str
    kind: str
    extractor: str
    context: str


def build_index(conn: sqlite3.Connection, repos: list[str] | None = None) -> dict[str, int]:
    """(Re)build `agreement_tokens` from all stored occurrences (optionally restricted to some repos)."""
    repo_filter, params = "", []
    if repos:
        repo_filter = f" WHERE r.name IN ({','.join('?' * len(repos))})"
        params = list(repos)
    n_files = conn.execute(
        "SELECT COUNT(DISTINCT f.id) FROM files f JOIN repos r ON r.id=f.repo_id" + repo_filter, params).fetchone()[0]
    rows = conn.execute(
        "SELECT o.token_norm, o.base, o.version, COUNT(DISTINCT o.file_id) AS nf, COUNT(DISTINCT f.repo_id) AS nr,"
        " COUNT(DISTINCT o.extractor) AS ne"
        " FROM occurrences o JOIN files f ON f.id=o.file_id JOIN repos r ON r.id=f.repo_id" + repo_filter +
        " GROUP BY o.token_norm HAVING nf >= 2", params).fetchall()
    out = []
    for tn, base, version, nf, nr, ne in rows:
        nt = NormToken(tn, base, version, tn.startswith("/"))
        spec = specificity(nt)
        rar = rarity(nf, n_files)
        spr = spread(nf, nr)
        # a token shared by different file kinds (e.g. python + yaml) is a stronger contract than intra-language reuse
        cross_kind = 1.0 if ne > 1 else 0.85
        score = math.sqrt(rar) * spec * spr * cross_kind
        if score > 0:
            out.append((tn, nf, nr, ne, rar, spr, spec, score))
    with transaction(conn):
        conn.execute("DELETE FROM agreement_tokens")
        conn.executemany("INSERT INTO agreement_tokens VALUES (?,?,?,?,?,?,?,?)", out)
    return {"files": n_files, "tokens": len(out)}


def token_scores(conn: sqlite3.Connection, norms: list[str]) -> dict[str, float]:
    if not norms:
        return {}
    res = {}
    for i in range(0, len(norms), 500):
        chunk = norms[i:i + 500]
        for tn, sc in conn.execute(
                f"SELECT token_norm, score FROM agreement_tokens WHERE token_norm IN ({','.join('?' * len(chunk))})", chunk):
            res[tn] = sc
    return res


def repo_group(conn: sqlite3.Connection, repo: str) -> str | None:
    r = conn.execute("SELECT group_name FROM repos WHERE name=?", (repo,)).fetchone()
    return r[0] if r else None


def holders(conn: sqlite3.Connection, token_norm: str, limit: int = 200, group: str | None = None) -> list[Holder]:
    """All occurrences of a token; with `group`, only in repositories of that workspace group."""
    rows = conn.execute(
        "SELECT r.name, f.path, o.line, o.token_norm, o.token_raw, o.kind, o.extractor, o.context"
        " FROM occurrences o JOIN files f ON f.id=o.file_id JOIN repos r ON r.id=f.repo_id"
        " WHERE o.token_norm=? AND (? IS NULL OR r.group_name=?) ORDER BY r.name, f.path, o.line LIMIT ?",
        (token_norm, group, group, limit)).fetchall()
    return [Holder(*r) for r in rows]


def file_tokens(conn: sqlite3.Connection, repo: str, path: str) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT o.token_norm, o.token_raw, o.line, o.kind, o.context FROM occurrences o"
        " JOIN files f ON f.id=o.file_id JOIN repos r ON r.id=f.repo_id WHERE r.name=? AND f.path=?",
        (repo, path)).fetchall()


def top_tokens(conn: sqlite3.Connection, limit: int = 50) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM agreement_tokens ORDER BY score DESC LIMIT ?", (limit,))]
