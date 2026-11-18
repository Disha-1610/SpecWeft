"""Repository scanning: enumerate files, run extractors, normalize tokens, persist occurrences."""
from __future__ import annotations

import fnmatch
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from . import gitutil
from .db import transaction
from .extract.registry import classify, extract
from .tokens import normalize, specificity

log = logging.getLogger(__name__)

EXCLUDED_DIRS = {".git", "node_modules", "vendor", "dist", "build", "__pycache__", ".venv", "venv", ".tox",
                 ".mypy_cache", ".pytest_cache", "site-packages", ".next", "coverage", "third_party"}
MAX_FILE_BYTES = 512 * 1024


@dataclass
class ScanStats:
    repo: str
    files_seen: int = 0
    files_extracted: int = 0
    occurrences: int = 0
    failures: list[tuple[str, str]] = field(default_factory=list)
    by_extractor: dict[str, int] = field(default_factory=dict)


def is_excluded(path: str, extra: Iterable[str] = ()) -> bool:
    parts = path.split("/")
    if any(p in EXCLUDED_DIRS for p in parts[:-1]):
        return True
    return any(fnmatch.fnmatch(path, pat) for pat in extra)


def _iter_worktree(root: Path) -> list[str]:
    if gitutil.is_repo(root):
        return gitutil.ls_files(root)
    out = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in EXCLUDED_DIRS]
        for fn in fns:
            out.append(Path(dp, fn).relative_to(root).as_posix())
    return out


def scan_repo(conn: sqlite3.Connection, root: str | Path, name: str | None = None, rev: str | None = None,
              exclude: Iterable[str] = (), group: str | None = None) -> ScanStats:
    """Scan a repository (working tree, or a specific revision when `rev` is set) and replace its occurrences."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"repository root not found: {root}")
    name = name or root.name
    stats = ScanStats(repo=name)
    exclude = list(exclude)
    paths = [p for p in (gitutil.ls_files(root, rev) if rev else _iter_worktree(root)) if not is_excluded(p, exclude)]
    paths = [p for p in paths if classify(p, "") is not None or p.lower().endswith((".yml", ".yaml", ".json"))]
    blobs: dict[str, bytes] = gitutil.read_blobs(root, rev, paths) if rev else {}
    rows: list[tuple[str, list[tuple]]] = []
    for path in paths:
        stats.files_seen += 1
        try:
            if rev:
                data = blobs.get(path)
                if data is None:
                    continue
            else:
                fp = root / path
                if not fp.is_file() or fp.stat().st_size > MAX_FILE_BYTES:
                    continue
                data = fp.read_bytes()
            if len(data) > MAX_FILE_BYTES or b"\0" in data[:8192]:
                continue
            kind, raw = extract(path, data)
        except Exception as e:  # malformed file: record, continue
            stats.failures.append((path, f"{type(e).__name__}: {str(e)[:200]}"))
            log.debug("extract failed for %s: %s", path, e)
            continue
        if kind is None:
            continue
        stats.files_extracted += 1
        occ, seen = [], set()
        for t in raw:
            nt = normalize(t.text)
            if nt is None or specificity(nt) <= 0:
                continue
            key = (nt.norm, t.line, t.kind)
            if key in seen:
                continue
            seen.add(key)
            occ.append((t.text[:200], nt.norm, nt.base, nt.version, t.kind, kind, t.line, t.col, t.context))
        stats.by_extractor[kind] = stats.by_extractor.get(kind, 0) + 1
        stats.occurrences += len(occ)
        rows.append((path, occ))

    head = rev or gitutil.head(root)
    with transaction(conn):
        cur = conn.execute("SELECT id FROM repos WHERE name=?", (name,)).fetchone()
        if cur:
            repo_id = cur[0]
            conn.execute("DELETE FROM files WHERE repo_id=?", (repo_id,))  # cascades to occurrences
            conn.execute("UPDATE repos SET root=?, head_sha=?, scanned_at=?, group_name=COALESCE(?, group_name) WHERE id=?",
                         (str(root), head, _now(), group, repo_id))
        else:
            repo_id = conn.execute("INSERT INTO repos(name, root, head_sha, scanned_at, group_name) VALUES (?,?,?,?,?)",
                                   (name, str(root), head, _now(), group or name)).lastrowid
        for path, occ in rows:
            fid = conn.execute("INSERT INTO files(repo_id, path) VALUES (?,?)", (repo_id, path)).lastrowid
            conn.executemany(
                "INSERT INTO occurrences(file_id, token_raw, token_norm, base, version, kind, extractor, line, col, context)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)", [(fid, *o) for o in occ])
    log.info("scanned %s: %d files, %d occurrences, %d failures", name, stats.files_extracted, stats.occurrences,
             len(stats.failures))
    return stats


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
