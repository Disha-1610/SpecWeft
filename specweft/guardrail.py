"""The finish-line guardrail: one check that human PRs and coding agents both run before they call a change done.

Agents forget the other files too. An agent renames an env var everywhere it looked, its tests pass, and it reports
success, while a Kubernetes manifest in another repo still reads the old name. `check()` looks at the working tree
(whoever produced it: a person, Claude Code, Codex, Cursor, Aider, a CI job), asks the ranker which files still hold
the tokens that changed, and returns a pass/fail verdict with evidence the agent can act on.

Interfaces that share it:
  * `specweft check` (CLI; exit code 1 on fail) — for any agent loop, pre-commit, pre-push or CI
  * `specweft.hook` (Claude Code Stop hook) — formats with `format_findings`, blocks with the same thresholds
"""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from . import gitutil
from .service import ServiceError, analyze, repo_root, resolve_repo

LEVELS = {"high": 2, "medium": 1}


def fails(confidence: str, fail_on: str) -> bool:
    """`fail_on` is 'high', 'medium' or 'never'."""
    return fail_on in LEVELS and LEVELS.get(confidence, 0) >= LEVELS[fail_on]


def format_findings(recs: list[dict], touched: set[str] | None = None, limit: int = 5,
                    header: str = "SpecWeft: files likely affected by these edits but not updated:") -> str:
    lines = []
    for r in recs[:limit]:
        rf = r["related_file"]
        seen = " (already viewed)" if touched and rf["path"] in touched else ""
        where = f'{rf["repo"]}:' if r.get("cross_repo") else ""
        loc = f':{rf["line"]}' if rf.get("line") else ""
        lines.append(f'- [{r["confidence"]}] {where}{rf["path"]}{loc}{seen} — {r["reason"]}')
    more = len(recs) - len(lines)
    return header + "\n" + "\n".join(lines) + (f"\n(+{more} more; run `specweft check --json` for all)" if more > 0 else "")


def check(conn: sqlite3.Connection, path: str = ".", base: str = "HEAD", fail_on: str | None = None,
          limit: int = 20) -> dict:
    """Check the working tree of the indexed repo containing `path` against `base` (default: uncommitted edits)."""
    fail_on = fail_on or os.environ.get("SPECWEFT_FAIL_ON", "high")
    repo = resolve_repo(conn, path)
    if repo is None:
        raise ServiceError(f"{Path(path).resolve()} is not inside an indexed repo; run `specweft scan` first")
    root = repo_root(conn, repo)
    if not gitutil.is_repo(root):
        raise ServiceError(f"{root} is not a git repository")
    try:
        diff = gitutil.diff_text(root, base)
    except gitutil.GitError as e:
        raise ServiceError(str(e)) from e
    if not diff.strip():
        return {"repo": repo, "base": base, "verdict": "pass", "changed_files": [], "findings": [],
                "message": "SpecWeft: no changes against " + base}
    res = analyze(conn, repo, diff, limit)
    changed = set(res.get("changed_files") or [])
    pending = [r for r in res["recommendations"]
               if not (r["related_file"]["repo"] == repo and r["related_file"]["path"] in changed)
               and r["confidence"] in LEVELS]
    blocking = [r for r in pending if fails(r["confidence"], fail_on)]
    verdict = "fail" if blocking else "pass"
    msg = (format_findings(pending) if pending else "SpecWeft: no other holders of the changed tokens need updating.")
    if blocking:
        msg += "\nUpdate these files, or say why each needs no change, before finishing."
    return {"repo": repo, "base": base, "fail_on": fail_on, "verdict": verdict, "changed_files": sorted(changed),
            "findings": pending, "blocking": len(blocking), "message": msg}
