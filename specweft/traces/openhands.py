"""Adapter: OpenHands trajectories (OpenAI-style messages with tool_calls, as in nebius/SWE-rebench-openhands-trajectories).

Assistant messages carry `tool_calls[].function{name, arguments(JSON str)}`; the matching `tool` message
(`tool_call_id`) carries the output. Tools: str_replace_editor{command: view|create|str_replace|insert|undo_edit, path},
execute_bash{command}, think, finish.
"""
from __future__ import annotations

import json
import re
from typing import Any

from ..models import NormalizedEvent, NormalizedSession
from .classify import command_kind, command_paths, exit_code_in, output_failed
from .swe_agent import patch_files

_CWD = re.compile(r"\[Current working directory: ([^\]]+)\]")


def _args(call: dict[str, Any]) -> dict[str, Any]:
    raw = (call.get("function") or {}).get("arguments")
    if isinstance(raw, dict):
        return raw
    try:
        val = json.loads(raw or "{}")
        return val if isinstance(val, dict) else {}
    except json.JSONDecodeError:
        return {}


def parse_row(row: dict[str, Any], idx: int = 0) -> NormalizedSession:
    msgs = row.get("trajectory") or row.get("messages") or []
    outputs = {m.get("tool_call_id"): str(m.get("content") or "") for m in msgs
               if m.get("role") == "tool" and m.get("tool_call_id")}
    events: list[NormalizedEvent] = []
    cwd = None

    def emit(kind: str, p: str | None, excerpt: str) -> None:
        events.append(NormalizedEvent(len(events), kind, None, p, excerpt[:300]))

    for m in msgs:
        if m.get("role") == "tool" and cwd is None and (mm := _CWD.search(str(m.get("content") or ""))):
            cwd = mm.group(1).strip()
        if m.get("role") != "assistant":
            continue
        calls = m.get("tool_calls") or []
        if isinstance(calls, str):
            try:
                calls = json.loads(calls)
            except json.JSONDecodeError:
                calls = []
        for call in calls:
            fn = (call.get("function") or {}).get("name", "")
            a = _args(call)
            out = outputs.get(call.get("id"), "")
            if fn == "str_replace_editor":
                c, p = a.get("command"), a.get("path")
                if not p:
                    continue
                if c == "view":
                    # viewing a directory is a search-like listing, viewing a file is a read
                    is_dir = out.startswith("Here's the files and directories")
                    emit("search" if is_dir else "read", None if is_dir else p, f"view {p}")
                elif c in ("create", "str_replace", "insert", "undo_edit"):
                    if not out.startswith("ERROR"):
                        emit("edit", p, f"{c} {p}")
            elif fn in ("execute_bash", "bash", "execute_ipython_cell"):
                cmd = str(a.get("command") or a.get("code") or "")
                kind = command_kind(cmd)
                if kind in ("test_run", "build_run"):
                    emit(kind, None, cmd)
                    if output_failed(out, exit_code=exit_code_in(out)) or (exit_code_in(out) == 0 and re.search(r"\b\d+ failed\b", out)):
                        emit("test_fail" if kind == "test_run" else "build_fail", None, out[-300:])
                elif kind in ("read", "edit"):
                    for p in command_paths(cmd):
                        emit(kind, p, cmd)
                elif kind == "search":
                    emit("search", None, cmd)
    resolved = bool(row.get("resolved"))
    instance = str(row.get("instance_id", f"unknown-{idx}"))
    return NormalizedSession("openhands", str(row.get("trajectory_id") or f"{instance}#{idx}"), row.get("repo"), events,
                             cwd=cwd, gold_files=patch_files(row.get("model_patch")) if resolved else None)
