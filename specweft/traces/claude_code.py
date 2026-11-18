"""Adapter: Claude Code session transcripts (`~/.claude/projects/<proj>/<session>.jsonl`)."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ..models import NormalizedEvent, NormalizedSession
from .classify import command_kind, command_paths, exit_code_in, output_failed

log = logging.getLogger(__name__)

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
READ_TOOLS = {"Read", "NotebookRead"}
SEARCH_TOOLS = {"Grep", "Glob", "LS"}
SHELL_TOOLS = {"Bash", "PowerShell"}


def _blocks(rec: dict[str, Any]) -> list[dict[str, Any]]:
    c = (rec.get("message") or {}).get("content")
    return [b for b in c if isinstance(b, dict)] if isinstance(c, list) else []


def _result_text(block: dict[str, Any]) -> str:
    c = block.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(x.get("text", "") for x in c if isinstance(x, dict))
    return ""


def parse_session(path: str | Path) -> NormalizedSession:
    """Parse one transcript. Malformed lines are skipped (logged), never fatal."""
    path = Path(path)
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", errors="replace") as fh:
        for i, line in enumerate(fh):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                log.debug("%s:%d malformed JSON line skipped", path.name, i + 1)
                continue
            if isinstance(rec, dict):
                records.append(rec)
    session_id = next((r.get("sessionId") for r in records if r.get("sessionId")), path.stem)
    cwd = next((r.get("cwd") for r in records if r.get("cwd")), None)
    started = next((r.get("timestamp") for r in records if r.get("timestamp")), None)

    results: dict[str, tuple[str, bool]] = {}
    for r in records:
        if r.get("type") != "user":
            continue
        for b in _blocks(r):
            if b.get("type") == "tool_result" and b.get("tool_use_id"):
                results[b["tool_use_id"]] = (_result_text(b), bool(b.get("is_error")))

    events: list[NormalizedEvent] = []
    seq = 0

    def emit(kind: str, p: str | None, excerpt: str, ts: str | None) -> None:
        nonlocal seq
        events.append(NormalizedEvent(seq, kind, None, p, excerpt[:300], ts))
        seq += 1

    for r in records:
        if r.get("type") != "assistant" or r.get("isSidechain"):
            continue
        ts = r.get("timestamp")
        for b in _blocks(r):
            if b.get("type") != "tool_use":
                continue
            name, inp = b.get("name", ""), b.get("input") or {}
            out, is_err = results.get(b.get("id", ""), ("", False))
            if name in EDIT_TOOLS:
                fp = inp.get("file_path") or inp.get("notebook_path")
                if fp and not (is_err and "has not been read" in out):
                    emit("edit", fp, f"{name} {fp}", ts)
            elif name in READ_TOOLS:
                fp = inp.get("file_path") or inp.get("notebook_path")
                if fp:
                    emit("read", fp, f"{name} {fp}", ts)
            elif name in SEARCH_TOOLS:
                emit("search", None, f"{name} {inp.get('pattern', '')} {inp.get('path', '')}".strip(), ts)
            elif name in SHELL_TOOLS:
                cmd = str(inp.get("command", ""))
                kind = command_kind(cmd)
                if kind is None:
                    continue
                if kind in ("test_run", "build_run"):
                    emit(kind, None, cmd, ts)
                    if "denied" not in out[:200] and output_failed(out, is_err, exit_code_in(out) if is_err else None):
                        emit("test_fail" if kind == "test_run" else "build_fail", None, out[-300:], ts)
                else:
                    paths = command_paths(cmd)
                    if paths:
                        for p in paths:
                            emit(kind, p, cmd, ts)
                    elif kind == "search":
                        emit("search", None, cmd, ts)
    return NormalizedSession("claude_code", str(session_id), None, events, started_at=started, cwd=cwd)


def discover(projects_dir: str | Path) -> list[Path]:
    """All top-level session transcripts under ~/.claude/projects (subagent files excluded)."""
    root = Path(projects_dir)
    return sorted(p for p in root.glob("*/*.jsonl") if p.is_file())
