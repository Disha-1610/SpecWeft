"""Thin wrappers over the git CLI (no shell)."""
from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(RuntimeError):
    pass


def git(root: str | Path, *args: str, input_bytes: bytes | None = None, check: bool = True) -> bytes:
    try:
        proc = subprocess.run(["git", "-C", str(root), "-c", "core.quotepath=off", *args],
                              input=input_bytes, capture_output=True, timeout=600)
    except FileNotFoundError as e:
        raise GitError("git executable not found") from e
    if check and proc.returncode != 0:
        raise GitError(f"git {' '.join(args[:3])} failed: {proc.stderr.decode('utf-8', 'replace').strip()[:500]}")
    return proc.stdout


def is_repo(root: str | Path) -> bool:
    try:
        return git(root, "rev-parse", "--is-inside-work-tree").strip() == b"true"
    except GitError:
        return False


def head(root: str | Path) -> str | None:
    try:
        return git(root, "rev-parse", "HEAD").decode().strip()
    except GitError:
        return None


def toplevel(path: str | Path) -> str | None:
    try:
        return git(path, "rev-parse", "--show-toplevel").decode().strip()
    except GitError:
        return None


def ls_files(root: str | Path, rev: str | None = None) -> list[str]:
    if rev:
        out = git(root, "ls-tree", "-r", "--name-only", "-z", rev)
    else:
        out = git(root, "ls-files", "-z", "--cached")
    return [p for p in out.decode("utf-8", "replace").split("\0") if p]


def read_blobs(root: str | Path, rev: str, paths: list[str]) -> dict[str, bytes]:
    """Read many files at a revision with one `git cat-file --batch` call."""
    if not paths:
        return {}
    req = "".join(f"{rev}:{p}\n" for p in paths).encode("utf-8")
    out = git(root, "cat-file", "--batch", input_bytes=req)
    res: dict[str, bytes] = {}
    pos = 0
    for p in paths:
        nl = out.index(b"\n", pos)
        header = out[pos:nl].decode("utf-8", "replace").split()
        pos = nl + 1
        if len(header) >= 2 and header[1] == "missing":
            continue
        size = int(header[2])
        res[p] = out[pos:pos + size]
        pos += size + 1
    return res


def commits(root: str | Path, rev_range: str, max_count: int | None = None, no_merges: bool = True) -> list[dict]:
    """Commits (oldest first) with changed paths (rename-aware)."""
    args = ["log", "--reverse", "--name-status", "-M", "--format=%x1e%H%x1f%ct%x1f%s", rev_range]
    if no_merges:
        args.insert(1, "--no-merges")
    if max_count:
        args.insert(1, f"--max-count={max_count}")
    out = git(root, *args).decode("utf-8", "replace")
    res = []
    for chunk in out.split("\x1e")[1:]:
        head_line, _, body = chunk.partition("\n")
        sha, ts, subject = head_line.split("\x1f", 2)
        files, renames = [], {}
        for line in body.splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and parts[0]:
                st = parts[0]
                if st.startswith("R") and len(parts) == 3:
                    renames[parts[1]] = parts[2]
                    files.append(parts[2])
                else:
                    files.append(parts[1])
        res.append({"sha": sha, "ts": int(ts), "subject": subject, "files": files, "renames": renames})
    return res


def diff_text(root: str | Path, a: str, b: str | None = None, unified: int = 3) -> str:
    args = ["diff", f"-U{unified}", "-M", a] + ([b] if b else [])
    return git(root, *args).decode("utf-8", "replace")


def show_commit(root: str | Path, sha: str, unified: int = 3) -> str:
    return git(root, "show", f"-U{unified}", "-M", "--format=", sha).decode("utf-8", "replace")
