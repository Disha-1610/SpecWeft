"""Application service layer shared by CLI, API and hook (one code path for every interface)."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from . import gitutil
from .diffs import analyze_diff
from .models import Recommendation
from .ranker import rank

REPORTS_DIR = Path(__file__).resolve().parent.parent / "data" / "reports"


class ServiceError(ValueError):
    pass


def repo_root(conn: sqlite3.Connection, repo: str) -> str | None:
    r = conn.execute("SELECT root FROM repos WHERE name=?", (repo,)).fetchone()
    return r[0] if r else None


def resolve_repo(conn: sqlite3.Connection, path: str) -> str | None:
    """Scanned repo whose root contains `path` (longest match), else None."""
    p = Path(path).resolve()
    best = None
    for name, root in conn.execute("SELECT name, root FROM repos"):
        try:
            p.relative_to(Path(root).resolve())
        except ValueError:
            continue
        if best is None or len(root) > len(best[1]):
            best = (name, root)
    return best[0] if best else None


def diff_for(conn: sqlite3.Connection, repo: str, commit: str | None = None, base: str | None = None) -> str:
    root = repo_root(conn, repo)
    if not root:
        raise ServiceError(f"unknown repo {repo!r}; scan it first")
    if not gitutil.is_repo(root):
        raise ServiceError(f"{root} is not a git repository")
    try:
        if commit:
            return gitutil.show_commit(root, commit)
        return gitutil.diff_text(root, base or "HEAD")
    except gitutil.GitError as e:
        raise ServiceError(str(e)) from e


def analyze(conn: sqlite3.Connection, repo: str, diff_text: str, limit: int = 20) -> dict:
    if repo_root(conn, repo) is None:
        raise ServiceError(f"unknown repo {repo!r}; scan it first")
    from .diffs import parse_unified_diff
    fds = parse_unified_diff(diff_text)
    if not fds:
        raise ServiceError("diff contains no file changes")
    changed = sorted({fd.old_path or fd.new_path for fd in fds if (fd.old_path or fd.new_path)})
    _, changes = analyze_diff(conn, diff_text, repo)
    recs = rank(conn, repo, changed, diff_text, limit=limit)
    return {"repo": repo, "changed_files": changed,
            "token_changes": [c.__dict__ for c in changes if c.change_type != "touched"][:200],
            "recommendations": [r.to_dict() for r in recs]}


def rank_files(conn: sqlite3.Connection, repo: str, files: list[str], diff_text: str | None = None,
               limit: int = 20) -> list[Recommendation]:
    if not files:
        raise ServiceError("no changed files given")
    return rank(conn, repo, files, diff_text, limit=limit)


def save_report(name: str, data: dict) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    p = REPORTS_DIR / f"{name}.json"
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return p


def list_reports() -> dict[str, dict]:
    if not REPORTS_DIR.exists():
        return {}
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(REPORTS_DIR.glob("*.json"))}
