"""Ingest trajectories from any source into the normalized `sessions` / `events` tables."""
from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Iterable

from .. import gitutil
from ..db import transaction
from ..models import NormalizedSession
from . import claude_code, openhands, swe_agent
from .paths import commit_at, infer_container_root, map_to_head, to_repo_relative

log = logging.getLogger(__name__)


def resolve_paths(s: NormalizedSession, repo_root: str | None = None) -> NormalizedSession:
    """Fill `event.path` with repo-relative (and, when a local git checkout is known, HEAD-relative) paths."""
    local_root = repo_root
    if s.source == "claude_code":
        if local_root is None and s.cwd:
            local_root = gitutil.toplevel(s.cwd) if Path(s.cwd).exists() else None
            local_root = local_root or s.cwd
        trace_root = local_root
        if s.repo_name is None and local_root:
            s.repo_name = Path(local_root).name
    else:
        trace_root = infer_container_root([e.raw_path for e in s.events if e.raw_path], s.cwd)
    if local_root and s.started_at and gitutil.is_repo(local_root):
        s.commit_sha = s.commit_sha or commit_at(str(local_root), s.started_at)
    for e in s.events:
        if not e.raw_path:
            continue
        rel = to_repo_relative(e.raw_path, trace_root, s.cwd)
        if rel and s.commit_sha and local_root:
            rel = map_to_head(rel, local_root, s.commit_sha)
        e.path = rel
    if s.gold_files:
        s.gold_files = [map_to_head(g, local_root, s.commit_sha) for g in s.gold_files]
    return s


def store_session(conn: sqlite3.Connection, s: NormalizedSession, instance_id: str | None = None) -> int:
    """Idempotent: re-ingesting the same (source, external_id) replaces the previous copy."""
    with transaction(conn):
        conn.execute("DELETE FROM sessions WHERE source=? AND external_id=?", (s.source, s.external_id))
        sid = conn.execute(
            "INSERT INTO sessions(source, external_id, repo_name, commit_sha, started_at, n_events, gold_files, instance_id)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (s.source, s.external_id, s.repo_name, s.commit_sha, s.started_at, len(s.events),
             json.dumps(s.gold_files) if s.gold_files is not None else None,
             instance_id or s.external_id.split("#")[0])).lastrowid
        conn.executemany("INSERT INTO events(session_id, seq, kind, path, raw_path, excerpt, ts) VALUES (?,?,?,?,?,?,?)",
                         [(sid, e.seq, e.kind, e.path, e.raw_path, e.excerpt, e.ts) for e in s.events])
    return sid


def load_rows(path: str | Path) -> list[dict]:
    """Rows from a datasets-server JSON dump (`{"rows":[{"row":{...}}]}`), a JSON list, or JSONL."""
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return [json.loads(l) for l in text.splitlines() if l.strip()]
    if isinstance(data, dict) and "rows" in data:
        return [r.get("row", r) for r in data["rows"]]
    if isinstance(data, dict):
        return [data]
    return list(data)


def ingest_file(conn: sqlite3.Connection, source: str, path: str | Path, repo_root: str | None = None,
                repo_name: str | None = None) -> dict[str, int]:
    stats = {"sessions": 0, "events": 0, "skipped": 0}
    sessions: Iterable[NormalizedSession]
    if source == "claude_code":
        sessions = [claude_code.parse_session(path)]
    elif source in ("swe_agent", "openhands"):
        mod = swe_agent if source == "swe_agent" else openhands
        sessions = []
        for i, row in enumerate(load_rows(path)):
            try:
                sessions.append(mod.parse_row(row, i))
            except Exception as e:  # one malformed trajectory must not abort the batch
                log.warning("skipping malformed %s row %d: %s", source, i, e)
                stats["skipped"] += 1
    else:
        raise ValueError(f"unknown trajectory source {source!r}")
    for s in sessions:
        if repo_name:
            s.repo_name = repo_name
        s = resolve_paths(s, repo_root)
        store_session(conn, s)
        stats["sessions"] += 1
        stats["events"] += len(s.events)
    return stats
