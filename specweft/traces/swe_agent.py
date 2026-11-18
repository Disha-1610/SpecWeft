"""Adapter: SWE-agent trajectories (nebius/SWE-agent-trajectories row format; also classic .traj files).

Row format: {instance_id, trajectory: [{role: system|user|ai, text}], generated_patch, target(bool resolved)}.
Classic .traj: {trajectory: [{action, observation, ...}], info: {submission}}.
The agent's command is the last fenced block of an `ai` turn; the next `user` turn is its observation, which ends
with `(Open file: <path>)` / `(Current directory: <dir>)`.
"""
from __future__ import annotations

import re
import shlex
from typing import Any

from ..models import NormalizedEvent, NormalizedSession
from .classify import command_kind, command_paths, output_failed

_FENCE = re.compile(r"```(?:\w+)?\n(.*?)```", re.S)
_OPEN_FILE = re.compile(r"\(Open file: ([^)]*)\)")
_CWD = re.compile(r"\(Current directory: ([^)]*)\)")
_PATCH_FILES = re.compile(r"^diff --git a/(\S+) b/(\S+)", re.M)


def patch_files(patch: str | None) -> list[str]:
    seen: list[str] = []
    for a, b in _PATCH_FILES.findall(patch or ""):
        if b not in seen:
            seen.append(b)
    return seen


def instance_repo(instance_id: str) -> str:
    """`Owner__repo-123` -> `Owner/repo`."""
    base = instance_id.rsplit("-", 1)[0]
    return base.replace("__", "/", 1)


def _steps_from_row(traj: list[dict[str, Any]]) -> list[tuple[str, str]]:
    """(action, observation) pairs."""
    steps: list[tuple[str, str]] = []
    pending: str | None = None
    for turn in traj:
        role = turn.get("role")
        text = turn.get("text") or ""
        if role == "ai":
            blocks = _FENCE.findall(text)
            pending = blocks[-1].strip() if blocks else None
        elif role == "user" and pending is not None:
            steps.append((pending, text))
            pending = None
    if pending is not None:
        steps.append((pending, ""))
    return steps


def parse_row(row: dict[str, Any], idx: int = 0) -> NormalizedSession:
    traj = row.get("trajectory") or []
    if traj and "action" in traj[0]:  # classic .traj
        steps = [(str(s.get("action", "")), str(s.get("observation", ""))) for s in traj]
    else:
        steps = _steps_from_row(traj)
    instance = str(row.get("instance_id", f"unknown-{idx}"))
    events: list[NormalizedEvent] = []
    open_file: str | None = None
    cwd: str | None = None

    def emit(kind: str, p: str | None, excerpt: str) -> None:
        events.append(NormalizedEvent(len(events), kind, None, p, excerpt[:300]))

    for action, obs in steps:
        first = action.splitlines()[0].strip() if action else ""
        try:
            argv = shlex.split(first)
        except ValueError:
            argv = first.split()
        cmd = argv[0] if argv else ""
        if cmd == "open" and len(argv) > 1:
            open_file = argv[1]
            emit("read", open_file, first)
        elif cmd in ("goto", "scroll_down", "scroll_up") and open_file:
            emit("read", open_file, first)
        elif cmd == "create" and len(argv) > 1:
            open_file = argv[1]
            emit("edit", open_file, first)
        elif cmd == "edit" and open_file:
            emit("edit", open_file, first)
        elif cmd in ("search_file",):
            emit("search", argv[2] if len(argv) > 2 else open_file, first)
        elif cmd in ("search_dir", "find_file"):
            emit("search", None, first)
        elif cmd == "submit":
            pass
        else:
            kind = command_kind(action)
            if kind in ("test_run", "build_run"):
                emit(kind, None, first)
                if output_failed(obs):
                    emit("test_fail" if kind == "test_run" else "build_fail", None, obs[:300])
            elif kind in ("read", "edit"):
                for p in command_paths(first):
                    emit(kind, p, first)
            elif kind == "search":
                emit("search", None, first)
            elif re.match(r"^python\d*\s+\S+\.py", first):  # running a script = ad-hoc test
                emit("test_run", None, first)
                if output_failed(obs):
                    emit("test_fail", None, obs[:300])
        if m := _OPEN_FILE.search(obs or ""):
            v = m.group(1).strip()
            open_file = None if v in ("n/a", "") else v
        if m := _CWD.search(obs or ""):
            cwd = cwd or m.group(1).strip()
    patch = row.get("generated_patch") or (row.get("info") or {}).get("submission")
    resolved = bool(row.get("target"))
    traj_id = f"{instance}#{idx}"
    s = NormalizedSession("swe_agent", traj_id, instance_repo(instance), events, cwd=cwd,
                          gold_files=patch_files(patch) if resolved else None)
    return s
