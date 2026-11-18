"""Repository-relative and commit-aware path mapping for trajectory events."""
from __future__ import annotations

import posixpath
import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from .. import gitutil

_MSYS = re.compile(r"^/([a-zA-Z])/(.*)$")       # /c/Users/... (Git Bash)
_DRIVE = re.compile(r"^([a-zA-Z]):/(.*)$")


def canon(p: str) -> str:
    """Canonical absolute-or-relative POSIX form: backslashes -> '/', MSYS drives -> 'C:/', no trailing '/'."""
    p = p.strip().strip("'\"").replace("\\", "/")
    if m := _MSYS.match(p):
        p = f"{m.group(1).upper()}:/{m.group(2)}"
    elif m := _DRIVE.match(p):
        p = f"{m.group(1).upper()}:/{m.group(2)}"
    p = re.sub(r"/{2,}", "/", p)
    return p.rstrip("/") if len(p) > 1 else p


def _is_abs(p: str) -> bool:
    return p.startswith("/") or bool(_DRIVE.match(p))


def to_repo_relative(raw: str, root: str | None, cwd: str | None = None) -> str | None:
    """Map a path seen in a trajectory to a path relative to `root`; None if it lies outside the repo."""
    if not raw:
        return None
    p = canon(raw)
    base = canon(cwd) if cwd else (canon(root) if root else None)
    if not _is_abs(p):
        if base is None:
            return posixpath.normpath(p).lstrip("./") or None
        p = posixpath.join(base, p)
    p = posixpath.normpath(p)  # "C:/a/../b" -> "C:/b" (the drive is just a leading component)
    if root is None:
        return None
    r = canon(root)
    if p.lower() == r.lower():
        return None
    if p.lower().startswith(r.lower() + "/"):
        rel = p[len(r) + 1:]
        return rel or None
    return None


def infer_container_root(paths: list[str], cwd: str | None) -> str | None:
    """Root for sandboxed agent runs (`/lexicon`, `/workspace/owner__repo__x`): the cwd, else the most common
    first one/two path components."""
    if cwd:
        return canon(cwd)
    counts: dict[str, int] = {}
    for p in paths:
        c = canon(p)
        if not c.startswith("/"):
            continue
        parts = c.strip("/").split("/")
        key = "/" + "/".join(parts[:2] if parts[0] == "workspace" and len(parts) > 2 else parts[:1])
        counts[key] = counts.get(key, 0) + 1
    return max(counts, key=counts.get) if counts else None


@lru_cache(maxsize=256)
def commit_at(repo_root: str, iso_ts: str) -> str | None:
    """Last commit on HEAD at or before the timestamp (the code the session actually saw)."""
    try:
        ts = datetime.fromisoformat(iso_ts.replace("Z", "+00:00")).isoformat()
        out = gitutil.git(repo_root, "rev-list", "-1", f"--before={ts}", "HEAD").decode().strip()
        return out or None
    except (gitutil.GitError, ValueError):
        return None


@lru_cache(maxsize=256)
def rename_map(repo_root: str, from_rev: str, to_rev: str = "HEAD") -> dict[str, str]:
    """old path -> path at `to_rev` (git rename detection); deleted files map to themselves."""
    try:
        out = gitutil.git(repo_root, "diff", "--name-status", "-M", from_rev, to_rev).decode("utf-8", "replace")
    except gitutil.GitError:
        return {}
    res = {}
    for line in out.splitlines():
        parts = line.split("\t")
        if parts and parts[0].startswith("R") and len(parts) == 3:
            res[parts[1]] = parts[2]
    return res


def map_to_head(rel: str, repo_root: str | None, commit: str | None) -> str:
    """Commit-aware mapping: a path as it existed at `commit` -> its current name at HEAD."""
    if not rel or not repo_root or not commit:
        return rel
    return rename_map(str(Path(repo_root)), commit).get(rel, rel)
