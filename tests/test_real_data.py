"""Checks against the real downloaded data (skipped when data/ is not populated)."""
from pathlib import Path

import pytest

from specweft.traces import claude_code, openhands, swe_agent
from specweft.traces.ingest import load_rows

DATA = Path(__file__).resolve().parent.parent / "data"
SWE = DATA / "trajectories" / "sweagent_rows.json"
OH = DATA / "trajectories" / "openhands_rows.json"


@pytest.mark.skipif(not SWE.exists(), reason="real SWE-agent sample not downloaded")
def test_real_swe_agent_rows_parse():
    rows = load_rows(SWE)
    sessions = [swe_agent.parse_row(r, i) for i, r in enumerate(rows)]
    assert len(sessions) == len(rows) == 100
    assert sum(len(s.events) for s in sessions) > 1000
    assert all(any(e.kind == "edit" for e in s.events) for s in sessions if s.gold_files)


@pytest.mark.skipif(not OH.exists(), reason="real OpenHands sample not downloaded")
def test_real_openhands_rows_parse():
    rows = load_rows(OH)
    sessions = [openhands.parse_row(r, i) for i, r in enumerate(rows)]
    kinds = {e.kind for s in sessions for e in s.events}
    assert {"read", "edit", "test_run", "test_fail"} <= kinds


@pytest.mark.skipif(not (Path.home() / ".claude" / "projects").is_dir(), reason="no local Claude Code transcripts")
def test_real_claude_transcripts_parse():
    files = claude_code.discover(Path.home() / ".claude" / "projects")[:20]
    for f in files:
        s = claude_code.parse_session(f)
        assert s.external_id
