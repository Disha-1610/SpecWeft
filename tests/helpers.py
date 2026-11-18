"""Builders for trajectory test fixtures in each source's real on-disk schema."""
from __future__ import annotations

import json
from pathlib import Path


def claude_transcript(path: Path, cwd: str, steps: list[tuple[str, dict, str, bool]], session_id: str = "sess-1",
                      ts: str | None = None) -> Path:
    """steps: (tool_name, input, result_text, is_error) -> Claude Code JSONL (assistant tool_use + user tool_result)."""
    if ts is None:  # "now": after the fixture repo's commits, so commit-aware mapping finds a commit
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    lines = [{"type": "user", "sessionId": session_id, "cwd": cwd, "timestamp": ts,
              "message": {"role": "user", "content": "do the task"}}]
    for i, (name, inp, out, err) in enumerate(steps):
        tid = f"toolu_{i}"
        lines.append({"type": "assistant", "sessionId": session_id, "cwd": cwd, "timestamp": ts, "isSidechain": False,
                      "message": {"role": "assistant", "content": [{"type": "tool_use", "id": tid, "name": name, "input": inp}]}})
        lines.append({"type": "user", "sessionId": session_id, "cwd": cwd, "timestamp": ts,
                      "message": {"role": "user", "content": [{"type": "tool_result", "tool_use_id": tid, "content": out,
                                                               "is_error": err}]}})
    path.write_text("\n".join(json.dumps(l) for l in lines) + "\n{not json\n", encoding="utf-8")
    return path


def swe_agent_row(instance: str, actions: list[tuple[str, str]], patch: str = "", resolved: bool = True) -> dict:
    traj = [{"role": "system", "text": "SETTING"}, {"role": "user", "text": "ISSUE"}]
    for act, obs in actions:
        traj.append({"role": "ai", "text": f"thinking\n```\n{act}\n```"})
        traj.append({"role": "user", "text": obs})
    return {"instance_id": instance, "trajectory": traj, "generated_patch": patch, "target": resolved}


def openhands_row(repo: str, calls: list[tuple[str, dict, str]], patch: str = "", resolved: int = 1) -> dict:
    msgs = [{"role": "system", "content": "You are OpenHands"}, {"role": "user", "content": "task"}]
    for i, (fn, args, out) in enumerate(calls):
        msgs.append({"role": "assistant", "content": "", "tool_calls": [
            {"id": f"c{i}", "type": "function", "function": {"name": fn, "arguments": json.dumps(args)}}]})
        msgs.append({"role": "tool", "name": fn, "tool_call_id": f"c{i}", "content": out})
    return {"trajectory_id": f"t-{repo}-{len(calls)}", "instance_id": repo.replace("/", "__") + "-1", "repo": repo,
            "trajectory": msgs, "model_patch": patch, "resolved": resolved}
