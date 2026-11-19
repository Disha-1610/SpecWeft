"""SQLite storage: connection management and schema migrations."""
from __future__ import annotations

import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

log = logging.getLogger(__name__)

DEFAULT_DB = os.environ.get("SPECWEFT_DB", str(Path(__file__).resolve().parent.parent / "data" / "specweft.db"))

MIGRATIONS: list[str] = [
    # v1
    """
    CREATE TABLE repos(
        id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, root TEXT NOT NULL,
        head_sha TEXT, scanned_at TEXT);
    CREATE TABLE files(
        id INTEGER PRIMARY KEY, repo_id INTEGER NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
        path TEXT NOT NULL, UNIQUE(repo_id, path));
    CREATE TABLE occurrences(
        id INTEGER PRIMARY KEY, file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
        token_raw TEXT NOT NULL, token_norm TEXT NOT NULL, base TEXT NOT NULL, version TEXT,
        kind TEXT NOT NULL, extractor TEXT NOT NULL, line INTEGER NOT NULL, col INTEGER NOT NULL,
        context TEXT);
    CREATE INDEX ix_occ_norm ON occurrences(token_norm);
    CREATE INDEX ix_occ_file ON occurrences(file_id);
    CREATE TABLE agreement_tokens(
        token_norm TEXT PRIMARY KEY, n_files INTEGER NOT NULL, n_repos INTEGER NOT NULL,
        n_extractors INTEGER NOT NULL, rarity REAL NOT NULL, spread REAL NOT NULL,
        specificity REAL NOT NULL, score REAL NOT NULL);
    CREATE TABLE sessions(
        id INTEGER PRIMARY KEY, source TEXT NOT NULL, external_id TEXT NOT NULL,
        repo_name TEXT, commit_sha TEXT, started_at TEXT, n_events INTEGER DEFAULT 0,
        gold_files TEXT, instance_id TEXT, UNIQUE(source, external_id));
    CREATE TABLE events(
        id INTEGER PRIMARY KEY, session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
        seq INTEGER NOT NULL, kind TEXT NOT NULL, path TEXT, raw_path TEXT, excerpt TEXT, ts TEXT,
        UNIQUE(session_id, seq));
    CREATE INDEX ix_events_path ON events(path);
    CREATE TABLE nav_edges(
        repo_name TEXT NOT NULL, src TEXT NOT NULL, dst TEXT NOT NULL, n_sessions INTEGER NOT NULL,
        n_detour INTEGER NOT NULL, p_cond REAL NOT NULL, lift REAL NOT NULL, score REAL NOT NULL,
        last_ts TEXT, sample_sessions TEXT, PRIMARY KEY(repo_name, src, dst));
    CREATE INDEX ix_nav_src ON nav_edges(repo_name, src);
    CREATE TABLE nav_baseline(
        repo_name TEXT NOT NULL, path TEXT NOT NULL, n_sessions INTEGER NOT NULL, rate REAL NOT NULL,
        PRIMARY KEY(repo_name, path));
    CREATE TABLE nav_sources(
        repo_name TEXT NOT NULL, path TEXT NOT NULL, n_sessions INTEGER NOT NULL,
        PRIMARY KEY(repo_name, path));
    CREATE TABLE cochange(
        repo_name TEXT NOT NULL, a TEXT NOT NULL, b TEXT NOT NULL, n INTEGER NOT NULL, n_a INTEGER NOT NULL,
        PRIMARY KEY(repo_name, a, b));
    CREATE TABLE replay_labels(
        id INTEGER PRIMARY KEY, run TEXT NOT NULL, repo_name TEXT NOT NULL, commit_sha TEXT NOT NULL,
        seed TEXT NOT NULL, candidate TEXT NOT NULL, features TEXT NOT NULL, label INTEGER NOT NULL,
        UNIQUE(run, commit_sha, seed, candidate));
    CREATE TABLE models(
        name TEXT PRIMARY KEY, params TEXT NOT NULL, trained_at TEXT NOT NULL,
        n_samples INTEGER NOT NULL, metrics TEXT);
    """,
    # v2: workspace groups — cross-repo agreements only count between repos of the same system
    """
    ALTER TABLE repos ADD COLUMN group_name TEXT;
    UPDATE repos SET group_name = name WHERE group_name IS NULL;
    CREATE INDEX ix_repos_group ON repos(group_name);
    """,
    # v3: on-demand indexing jobs (Forge app: repos are cloned + scanned the first time a PR is opened)
    """
    CREATE TABLE index_jobs(
        repo_name TEXT PRIMARY KEY, status TEXT NOT NULL, error TEXT, requested_at TEXT NOT NULL,
        started_at TEXT, finished_at TEXT, files INTEGER, head_sha TEXT);
    """,
]


def connect(path: str | None = None) -> sqlite3.Connection:
    """Open the database and apply pending migrations."""
    path = path or DEFAULT_DB
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA journal_mode=WAL") if path != ":memory:" else None
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection) -> None:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version(v INTEGER NOT NULL)")
    row = conn.execute("SELECT v FROM schema_version").fetchone()
    current = row[0] if row else 0
    for i, sql in enumerate(MIGRATIONS[current:], start=current + 1):
        log.info("applying migration v%d", i)
        conn.executescript("BEGIN;" + sql + "COMMIT;")
        conn.execute("DELETE FROM schema_version")
        conn.execute("INSERT INTO schema_version(v) VALUES (?)", (i,))
        conn.commit()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Explicit transaction; rolls back on any exception."""
    conn.execute("BEGIN")
    try:
        yield conn
    except BaseException:
        conn.rollback()
        raise
    else:
        conn.commit()
