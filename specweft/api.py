"""HTTP API + static web UI. Every endpoint returns the shared evidence schema for recommendations."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Iterator

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, model_validator

from . import db, service
from .agreements import holders, top_tokens
from .navigation import neighbors
from .tokens import normalize

WEB = Path(__file__).resolve().parent / "web" / "index.html"
app = FastAPI(title="SpecWeft", version="1.0.0",
              description="Broken Agreements + Waze for Code: evidence-backed change-impact recommendations.")


def get_conn() -> Iterator[sqlite3.Connection]:  # noqa: D401
    conn = db.connect(app.state.db_path if hasattr(app.state, "db_path") else None)
    try:
        yield conn
    finally:
        conn.close()


class AnalyzeRequest(BaseModel):
    repo: str = Field(min_length=1)
    diff: str | None = Field(default=None, max_length=5_000_000)
    commit: str | None = Field(default=None, pattern=r"^[0-9A-Za-z_./~^\-]{1,100}$")
    limit: int = Field(default=20, ge=1, le=200)

    @model_validator(mode="after")
    def one_source(self) -> "AnalyzeRequest":
        if bool(self.diff) == bool(self.commit):
            raise ValueError("provide exactly one of `diff` or `commit`")
        return self


class RankRequest(BaseModel):
    repo: str = Field(min_length=1)
    changed_files: list[str] = Field(min_length=1, max_length=500)
    diff: str | None = Field(default=None, max_length=5_000_000)
    limit: int = Field(default=20, ge=1, le=200)


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(WEB)


@app.api_route("/api/health", methods=["GET", "HEAD"])  # HEAD: uptime monitors (UptimeRobot) probe with it
def health(conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    c = lambda t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]  # table names are constants
    m = conn.execute("SELECT name, n_samples, trained_at FROM models WHERE name='fusion_lr'").fetchone()
    return {"status": "ok", "repos": c("repos"), "files": c("files"), "occurrences": c("occurrences"),
            "agreement_tokens": c("agreement_tokens"), "sessions": c("sessions"), "events": c("events"),
            "nav_edges": c("nav_edges"), "model": dict(m) if m else None}


@app.get("/api/repos")
def repos(conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT r.name, r.root, r.head_sha, r.scanned_at, COUNT(f.id) AS files FROM repos r"
        " LEFT JOIN files f ON f.repo_id=r.id GROUP BY r.id ORDER BY r.name")]


@app.get("/api/agreements/top")
def agreements_top(limit: int = Query(50, ge=1, le=1000), conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    return top_tokens(conn, limit)


@app.get("/api/agreements/holders")
def agreement_holders(token: str = Query(min_length=1, max_length=200), conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    nt = normalize(token)
    if nt is None:
        raise HTTPException(422, "token is not a valid agreement token")
    meta = conn.execute("SELECT * FROM agreement_tokens WHERE token_norm=?", (nt.norm,)).fetchone()
    return {"token": nt.norm, "agreement": dict(meta) if meta else None,
            "holders": [h.__dict__ for h in holders(conn, nt.norm)]}


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    try:
        diff = req.diff or service.diff_for(conn, req.repo, commit=req.commit)
        return service.analyze(conn, req.repo, diff, req.limit)
    except service.ServiceError as e:
        raise HTTPException(422, str(e)) from e


@app.post("/api/rank")
def rank(req: RankRequest, conn: sqlite3.Connection = Depends(get_conn)) -> dict:
    try:
        recs = service.rank_files(conn, req.repo, req.changed_files, req.diff, req.limit)
    except service.ServiceError as e:
        raise HTTPException(422, str(e)) from e
    return {"repo": req.repo, "changed_files": req.changed_files, "recommendations": [r.to_dict() for r in recs]}


@app.get("/api/navigation")
def navigation(repo: str, src: str, conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    return neighbors(conn, repo, src)


@app.get("/api/sessions")
def sessions(limit: int = Query(100, ge=1, le=5000), conn: sqlite3.Connection = Depends(get_conn)) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT id, source, external_id, repo_name, commit_sha, started_at, n_events, gold_files IS NOT NULL AS has_gold"
        " FROM sessions ORDER BY id LIMIT ?", (limit,))]


@app.get("/api/reports")
def reports() -> dict:
    return service.list_reports()


from .forge import router as forge_router  # noqa: E402

app.include_router(forge_router)


def serve(host: str = "127.0.0.1", port: int = 8765, db_path: str | None = None) -> None:
    import uvicorn
    app.state.db_path = db_path
    uvicorn.run(app, host=host, port=port)
