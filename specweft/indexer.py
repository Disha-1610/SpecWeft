"""On-demand indexing of Bitbucket repositories for the Forge app.

The first time a pull request in an unknown repo is analyzed, a background job clones the repo and builds its
agreement index; callers get status "indexing" and poll. Safety rules:
  * the clone URL is built server-side from a validated `workspace/slug` (never taken from the request)
  * only public HTTPS clones (no credentials); private repos fail with a clear message
  * one job per repo at a time; bounded concurrency; clone time and checkout size are capped
  * an index older than SPECWEFT_INDEX_TTL_HOURS is refreshed in the background (old results stay served meanwhile)
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from . import db
from .agreements import build_index
from .scanner import scan_repo

log = logging.getLogger(__name__)

FULL_NAME = re.compile(r"^[A-Za-z0-9_.\-]{1,100}/[A-Za-z0-9_.\-]{1,100}$")
CLONE_TIMEOUT_S = int(os.environ.get("SPECWEFT_CLONE_TIMEOUT", "180"))
MAX_REPO_MB = int(os.environ.get("SPECWEFT_MAX_REPO_MB", "300"))
HISTORY_DEPTH = int(os.environ.get("SPECWEFT_CLONE_DEPTH", "500"))
_pool = ThreadPoolExecutor(max_workers=int(os.environ.get("SPECWEFT_INDEX_WORKERS", "2")))
_lock = threading.Lock()


class IndexError_(ValueError):
    pass


def repos_dir() -> Path:
    return Path(os.environ.get("SPECWEFT_REPOS_DIR", Path(db.DEFAULT_DB).parent / "repos" / "bitbucket"))


def clone_url(full_name: str) -> str:
    if not FULL_NAME.match(full_name) or ".." in full_name:
        raise IndexError_(f"invalid repository name {full_name!r}")
    # operator-controlled base (tests use a local file:// mirror); never derived from a request
    base = os.environ.get("SPECWEFT_GIT_BASE", "https://bitbucket.org").rstrip("/")
    return f"{base}/{full_name}.git"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def job_status(conn, repo_name: str) -> dict | None:
    r = conn.execute("SELECT * FROM index_jobs WHERE repo_name=?", (repo_name,)).fetchone()
    return dict(r) if r else None


def is_stale(conn, repo_name: str) -> bool:
    ttl = float(os.environ.get("SPECWEFT_INDEX_TTL_HOURS", "24"))
    r = conn.execute("SELECT scanned_at FROM repos WHERE name=?", (repo_name,)).fetchone()
    if not r or not r[0]:
        return True
    return datetime.fromisoformat(r[0]) < datetime.now(timezone.utc) - timedelta(hours=ttl)


def request_index(conn, full_name: str, db_path: str | None = None,
                  runner: Callable[[str, str | None], None] | None = None) -> dict:
    """Queue an index job unless one is queued/running. Returns the job row."""
    clone_url(full_name)  # validate early
    with _lock:
        cur = job_status(conn, full_name)
        if cur and cur["status"] in ("queued", "running"):
            return cur
        with conn:
            conn.execute("INSERT OR REPLACE INTO index_jobs(repo_name, status, requested_at) VALUES (?,?,?)",
                         (full_name, "queued", _now()))
    (_pool.submit if runner is None else (lambda f, *a: f(*a)))(runner or run_index_job, full_name, db_path)
    return job_status(conn, full_name)


def _git(args: list[str], cwd: Path | None = None) -> None:
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_ASKPASS="echo")  # never prompt for credentials
    p = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=CLONE_TIMEOUT_S, env=env)
    if p.returncode != 0:
        msg = p.stderr.strip()[-400:]
        if "Authentication failed" in msg or "could not read Username" in msg or "not found" in msg.lower():
            raise IndexError_("repository is private or not reachable without credentials; "
                              "SpecWeft can only index public repositories on demand")
        raise IndexError_(f"git {args[0]} failed: {msg}")


def _dir_mb(path: Path) -> float:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1e6


def run_index_job(full_name: str, db_path: str | None = None) -> None:
    conn = db.connect(db_path)
    try:
        with conn:
            conn.execute("UPDATE index_jobs SET status='running', started_at=?, error=NULL WHERE repo_name=?",
                         (_now(), full_name))
        target = repos_dir() / full_name.replace("/", "__")
        tmp = target.with_name(target.name + ".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.parent.mkdir(parents=True, exist_ok=True)
        _git(["clone", "--quiet", f"--depth={HISTORY_DEPTH}", "--single-branch", clone_url(full_name), str(tmp)])
        if _dir_mb(tmp) > MAX_REPO_MB:
            shutil.rmtree(tmp, ignore_errors=True)
            raise IndexError_(f"repository larger than {MAX_REPO_MB} MB; index it manually with the CLI")
        shutil.rmtree(target, ignore_errors=True)
        tmp.rename(target)
        stats = scan_repo(conn, target, full_name, group=full_name.split("/")[0])
        build_index(conn)
        head = conn.execute("SELECT head_sha FROM repos WHERE name=?", (full_name,)).fetchone()[0]
        with conn:
            conn.execute("UPDATE index_jobs SET status='done', finished_at=?, files=?, head_sha=? WHERE repo_name=?",
                         (_now(), stats.files_extracted, head, full_name))
        log.info("indexed %s: %d files", full_name, stats.files_extracted)
    except Exception as e:  # recorded for the panel; never crashes the server
        log.warning("index job for %s failed: %s", full_name, e)
        msg = str(e) if isinstance(e, IndexError_) else f"{type(e).__name__}: {e}"
        with conn:
            conn.execute("UPDATE index_jobs SET status='failed', finished_at=?, error=? WHERE repo_name=?",
                         (_now(), msg[:500], full_name))
    finally:
        conn.close()
