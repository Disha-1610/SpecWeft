"""Agents forget the other files too.

A coding agent is asked to make the `orders-service` rename from the cross-repo demo. It edits every file in the repo
it is working in, and stops. The Claude Code Stop hook runs SpecWeft and sends the agent back with the files in
`checkout-web` and `platform-infra` that still hold the old names. `specweft check` gives any other agent (or a
human before `git push`) the same verdict from the working tree alone, with no transcript needed.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from . import agreements, cochange, db, guardrail, hook, scanner
from .crossrepo_demo import GROUP, PR_EDITS, _git, build_workspace

TASK = "Rename shipping_address_line -> shipping_address, ORDERS_PAYMENT_WEBHOOK_SECRET -> PAYMENTS_WEBHOOK_SECRET " \
       "and DATABASE_URL -> ORDERS_DATABASE_URL."


def _transcript(path: Path, root: Path, files: list[str]) -> Path:
    ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    base = {"sessionId": "agent-demo", "cwd": str(root), "timestamp": ts}
    lines = [base | {"type": "user", "message": {"role": "user", "content": TASK}}]
    i = 0
    for rel in files:
        for name in ("Read", "Edit"):
            inp = {"file_path": str(root / rel)} | ({"old_string": "...", "new_string": "..."} if name == "Edit" else {})
            lines.append(base | {"type": "assistant", "isSidechain": False, "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": f"toolu_{i}", "name": name, "input": inp}]}})
            lines.append(base | {"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": f"toolu_{i}", "content": "ok", "is_error": False}]}})
            i += 1
    path.write_text("\n".join(json.dumps(l) for l in lines) + "\n", encoding="utf-8")
    return path


def run(base: Path, db_path: Path) -> dict:
    roots = build_workspace(base)
    for suf in ("", "-wal", "-shm"):
        Path(str(db_path) + suf).unlink(missing_ok=True)
    conn = db.connect(str(db_path))
    try:
        for name, root in roots.items():
            scanner.scan_repo(conn, root, name, group=GROUP)
            cochange.store(conn, name, cochange.from_history(root, "main"))
        agreements.build_index(conn)
        conn.commit()
        o = roots["orders-service"]
        # the agent's work: the same edits as the demo PR, left uncommitted on main
        for rel, old, new in PR_EDITS:
            p = o / rel
            p.write_text(p.read_text(encoding="utf-8").replace(old, new), encoding="utf-8", newline="\n")
        edited = sorted({rel for rel, _, _ in PR_EDITS})
        t = _transcript(base / "agent-session.jsonl", o, edited)
        payload = {"session_id": "agent-demo", "transcript_path": str(t), "cwd": str(o), "hook_event_name": "Stop"}
        prev = os.environ.get("SPECWEFT_FAIL_ON")
        os.environ["SPECWEFT_FAIL_ON"] = "medium"  # cross-repo flags have one signal (agreement) on day one
        try:
            first = hook.run(payload | {"stop_hook_active": False}, str(db_path))
            second = hook.run(payload | {"stop_hook_active": True}, str(db_path))
        finally:
            if prev is None:
                os.environ.pop("SPECWEFT_FAIL_ON", None)
            else:
                os.environ["SPECWEFT_FAIL_ON"] = prev
        chk = guardrail.check(conn, str(o), "HEAD", "medium")
        stale = sorted({f'{r["related_file"]["repo"]}:{r["related_file"]["path"]}' for r in chk["findings"]})
        return {"task": TASK, "agent_edited": edited, "agent_repo": "orders-service",
                "stop_hook": {"first_stop": first.get("output"), "second_stop": second.get("output")},
                "check": {"verdict": chk["verdict"], "blocking": chk["blocking"], "stale_files": stale},
                "git_status": _git(o, "status", "--short").splitlines()}
    finally:
        conn.close()


def render(rep: dict) -> str:
    out = [f"TASK   {rep['task']}",
           f"AGENT  edited {len(rep['agent_edited'])} files in {rep['agent_repo']}: {', '.join(rep['agent_edited'])}",
           "AGENT  \"Done. All references renamed.\"", "",
           "Stop hook (1st stop) ->"]
    first = rep["stop_hook"]["first_stop"] or {}
    out.append(f"  decision: {first.get('decision', 'none')}")
    out += ["  " + l for l in (first.get("reason") or first.get("systemMessage") or "").splitlines()]
    second = rep["stop_hook"]["second_stop"] or {}
    out += ["", "Stop hook (2nd stop, stop_hook_active) -> " + ("block" if "decision" in second else "warn only; never blocks twice"),
            "", f"specweft check --fail-on medium -> {rep['check']['verdict'].upper()} "
                f"({len(rep['check']['stale_files'])} stale file(s) outside what the agent touched)"]
    out += [f"  X {f}" for f in rep["check"]["stale_files"]]
    return "\n".join(out)
