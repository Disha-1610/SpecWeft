"""Claude Code Stop hook.

Configure in `.claude/settings.json`:
  {"hooks": {"Stop": [{"hooks": [{"type": "command",
      "command": "python <SpecWeft>/scripts/specweft_hook.py --db <SpecWeft>/data/specweft.db"}]}]}}

Input (stdin JSON): session_id, transcript_path, cwd, hook_event_name, stop_hook_active.
Behaviour:
  * derive files edited in this session from the transcript (same adapter as ingestion)
  * diff them against HEAD when the repo is a git checkout (precise removed/renamed/value-changed tokens)
  * query the unified ranker; keep recommendations for files the session has NOT edited
  * output JSON: `{"decision": "block", "reason": ...}` only when there is ≥1 recommendation at or above
    SPECWEFT_FAIL_ON (default "high"; same threshold as `specweft check`),
    `stop_hook_active` is false and SPECWEFT_HOOK_MODE != "warn"; otherwise a non-blocking `systemMessage`.
  * any failure -> exit 0 with a note on stderr (never blocks completion because of SpecWeft itself).
Every invocation is appended to data/hook_log.jsonl for auditing.
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

LOG = Path(os.environ.get("SPECWEFT_HOOK_LOG", Path(__file__).resolve().parent.parent / "data" / "hook_log.jsonl"))


def run(payload: dict, db_path: str | None = None) -> dict:
    """Pure function used by `main` and tests. Returns {"output": dict|None, "recommendations": [...], ...}."""
    from . import db, gitutil
    from .service import resolve_repo
    from .ranker import rank
    from .traces import claude_code
    from .traces.ingest import resolve_paths

    transcript = payload.get("transcript_path")
    cwd = payload.get("cwd") or os.getcwd()
    if not transcript or not Path(transcript).is_file():
        return {"output": None, "status": "no_transcript"}
    conn = db.connect(db_path)
    try:
        repo = resolve_repo(conn, cwd)
        if repo is None:
            return {"output": None, "status": "repo_not_indexed", "cwd": cwd}
        root = conn.execute("SELECT root FROM repos WHERE name=?", (repo,)).fetchone()[0]
        session = claude_code.parse_session(transcript)
        session.repo_name = repo
        session = resolve_paths(session, repo_root=root)
        edited = list(dict.fromkeys(e.path for e in session.events if e.kind == "edit" and e.path))
        touched = {e.path for e in session.events if e.path and e.kind in ("edit", "read")}
        if not edited:
            return {"output": None, "status": "no_edits", "repo": repo}
        diff_text = None
        if gitutil.is_repo(root):
            try:
                diff_text = gitutil.git(root, "diff", "-U3", "-M", "HEAD", "--", *edited).decode("utf-8", "replace") or None
            except gitutil.GitError:
                diff_text = None
        recs = rank(conn, repo, edited, diff_text, limit=15)
        pending = [r for r in recs if not (r.related_file.repo == repo and r.related_file.path in edited)]
        actionable = [r for r in pending if r.confidence in ("high", "medium")]
        result = {"status": "ok", "repo": repo, "edited": edited,
                  "recommendations": [r.to_dict() for r in actionable[:8]]}
        if not actionable:
            result["output"] = None
            return result
        from .guardrail import fails, format_findings
        msg = format_findings([r.to_dict() for r in actionable], touched,
                              header="SpecWeft: files likely affected by this session's edits but not updated:")
        block_on = os.environ.get("SPECWEFT_FAIL_ON", "high")
        blocking = [r for r in actionable if fails(r.confidence, block_on)]
        mode = os.environ.get("SPECWEFT_HOOK_MODE", "block")
        if blocking and not payload.get("stop_hook_active") and mode != "warn":
            result["output"] = {"decision": "block",
                                "reason": msg + "\nCheck these files (or explain why no change is needed) before finishing."}
        else:
            result["output"] = {"systemMessage": msg}
        return result
    finally:
        conn.close()


def main(argv: list[str] | None = None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="specweft.hook")
    ap.add_argument("--db", default=None, help="SQLite DB (default $SPECWEFT_DB or data/specweft.db)")
    args, _ = ap.parse_known_args(argv)
    started = time.time()
    entry: dict = {"ts": started}
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            raise ValueError("hook input is not a JSON object")
        entry.update({k: payload.get(k) for k in ("session_id", "cwd", "hook_event_name", "stop_hook_active")})
        res = run(payload, args.db)
        entry.update({"status": res.get("status"), "n_recs": len(res.get("recommendations", [])),
                      "output": res.get("output")})
        if res.get("output"):
            sys.stdout.write(json.dumps(res["output"]))
    except Exception as e:  # never break the user's session
        entry.update({"status": "error", "error": f"{type(e).__name__}: {e}"})
        sys.stderr.write(f"specweft hook error (ignored): {e}\n")
        if os.environ.get("SPECWEFT_DEBUG"):
            traceback.print_exc()
    finally:
        entry["elapsed_s"] = round(time.time() - started, 3)
        try:
            LOG.parent.mkdir(parents=True, exist_ok=True)
            with LOG.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, default=str) + "\n")
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
