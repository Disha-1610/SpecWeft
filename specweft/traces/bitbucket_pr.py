"""Bitbucket pull-request history as navigation sessions ("where developers went next" on the customer's own repo).

Agent trajectories only exist for public benchmark repos. Every Bitbucket repo, though, has PR history, and a PR is
a recorded sequence of changes:

  * commit sequence  — files a developer changed in a later commit of the same PR are where they "went next" after
                       the files of the earlier commits (edge A→B for A in commit i, B in commit j > i).
  * review requests  — files changed after a reviewer commented are the files the review made them go back to. They
                       are recorded as detours, exactly like files touched after a failing test in an agent session.

One PR = one session (source `bitbucket_pr`). Events are stored in the normal `events` table:
  `commit` (excerpt = short sha + message) followed by one `edit` per file of that commit, and `review` events
  (path = the commented file, if the comment was inline) placed by timestamp. `navigation.analyze_pr_session` turns
  them into edges; the lift/score formulas are the same as for agent sessions.

Input (what the Forge app sends, one dict per PR):
  {"id": 12, "title": "...", "created_on": iso,
   "commits": [{"hash": "...", "date": iso, "message": "...", "files": ["a.py", ...]}, ...],   # any order
   "comments": [{"created_on": iso, "path": "a.py" | null}, ...]}                             # reviewer comments
The Forge app drops the author's own comments and sends no account ids. `author` / comment `user` are optional:
when both are given, comments by the author are ignored here too.
"""
from __future__ import annotations

from datetime import datetime

from ..models import NormalizedEvent, NormalizedSession

SOURCE = "bitbucket_pr"
MAX_COMMITS = 100
MAX_FILES_PER_COMMIT = 200   # larger commits are bulk renames / vendoring; they say nothing about navigation


def _ts(s: str | None) -> float:
    if not s:
        return 0.0
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _clean_path(p) -> str | None:
    if not isinstance(p, str):
        return None
    p = p.strip().replace("\\", "/").lstrip("/")
    if not p or len(p) > 1000 or any(x in ("", ".", "..") for x in p.split("/")):
        return None
    return p


def parse_pr(repo_full_name: str, pr: dict) -> NormalizedSession:
    """One PR -> one session. Raises ValueError on a PR without an id."""
    pr_id = pr.get("id")
    if not isinstance(pr_id, int) or pr_id < 1:
        raise ValueError("pull request without a valid id")
    commits = [c for c in (pr.get("commits") or []) if isinstance(c, dict)][:MAX_COMMITS]
    commits.sort(key=lambda c: _ts(c.get("date")))            # Bitbucket lists newest first
    author = pr.get("author")
    reviews = [c for c in (pr.get("comments") or []) if isinstance(c, dict)
               and (author is None or c.get("user") != author)]  # the author's own replies are not review requests
    reviews.sort(key=lambda c: _ts(c.get("created_on")))

    # merge commits and reviews into one timeline; a review at the same instant as a commit comes after it
    timeline: list[tuple[float, int, dict]] = [(_ts(c.get("date")), 0, c) for c in commits]
    timeline += [(_ts(r.get("created_on")), 1, r) for r in reviews]
    timeline.sort(key=lambda x: (x[0], x[1]))
    events: list[NormalizedEvent] = []
    seen_commit = False

    def emit(kind: str, path: str | None, excerpt: str, ts: str | None) -> None:
        events.append(NormalizedEvent(len(events), kind, path=path, raw_path=path, excerpt=excerpt[:300], ts=ts))

    for _, is_review, item in timeline:
        if is_review:
            if not seen_commit:          # a comment before any commit cannot have sent anyone anywhere
                continue
            path = _clean_path(item.get("path"))
            emit("review", path, f"review comment{' on ' + path if path else ''}", item.get("created_on"))
            continue
        files = [p for p in (_clean_path(f) for f in (item.get("files") or [])) if p]
        if not files or len(files) > MAX_FILES_PER_COMMIT:
            continue
        seen_commit = True
        sha = str(item.get("hash") or "")[:12]
        msg = str(item.get("message") or "").strip().splitlines()[0:1]
        emit("commit", None, f"PR #{pr_id} commit {sha}: {msg[0] if msg else ''}", item.get("date"))
        for p in dict.fromkeys(files):
            emit("edit", p, f"PR #{pr_id} commit {sha}", item.get("date"))
    return NormalizedSession(source=SOURCE, external_id=f"{repo_full_name}#{pr_id}", repo_name=repo_full_name,
                             events=events, commit_sha=None, started_at=pr.get("created_on"))
