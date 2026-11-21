"""Forge Remote endpoints: the Bitbucket Forge app calls these via `invokeRemote`.

Every request must carry a Forge Invocation Token (FIT) as `Authorization: Bearer <jwt>`. It is verified against
Atlassian's JWKS with issuer `forge/invocation-token` and audience = our Forge app id (SPECWEFT_FORGE_APP_ID).

Config (environment):
  SPECWEFT_FORGE_APP_ID     required, e.g. ari:cloud:ecosystem::app/<uuid> (from `forge register` / developer console)
  SPECWEFT_FORGE_JWKS_URL   default https://forge.cdn.prod.atlassian-dev.net/.well-known/jwks.json
  SPECWEFT_REPO_MAP         optional JSON {"<bitbucket repo slug or full_name>": "<scanned repo name>"}
  SPECWEFT_FORGE_AUTH       "off" disables verification — ONLY for local development; logged loudly.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
from functools import lru_cache

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from . import indexer, service
from .diffs import parse_unified_diff
from .ranker import rank

log = logging.getLogger(__name__)
router = APIRouter(prefix="/forge", tags=["forge"])

DEFAULT_JWKS = "https://forge.cdn.prod.atlassian-dev.net/.well-known/jwks.json"
ISSUER = "forge/invocation-token"
MAX_RECS = 25


@lru_cache(maxsize=4)
def _jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=3600)


def verify_fit(authorization: str | None = Header(default=None)) -> dict:
    """FastAPI dependency: validate the Forge Invocation Token, return its claims."""
    if os.environ.get("SPECWEFT_FORGE_AUTH", "").lower() == "off":
        log.warning("Forge FIT verification is DISABLED (SPECWEFT_FORGE_AUTH=off) — do not use in production")
        return {"auth": "disabled"}
    app_id = os.environ.get("SPECWEFT_FORGE_APP_ID")
    if not app_id:
        raise HTTPException(500, "server misconfigured: SPECWEFT_FORGE_APP_ID is not set")
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "missing Forge invocation token")
    token = authorization.split(" ", 1)[1].strip()
    try:
        key = _jwks_client(os.environ.get("SPECWEFT_FORGE_JWKS_URL", DEFAULT_JWKS)).get_signing_key_from_jwt(token)
        claims = jwt.decode(token, key.key, algorithms=["RS256"], audience=app_id, issuer=ISSUER,
                            options={"require": ["exp", "iat", "iss", "aud"]}, leeway=10)
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"invalid Forge invocation token: {e}") from e
    if (claims.get("app") or {}).get("id") not in (None, app_id):
        raise HTTPException(401, "token app id does not match this backend")
    return claims


def get_conn():
    from . import db
    from .api import app
    conn = db.connect(getattr(app.state, "db_path", None))
    try:
        yield conn
    finally:
        conn.close()


class PullRequestRef(BaseModel):
    repo_slug: str = Field(min_length=1, max_length=200)
    repo_full_name: str | None = Field(default=None, max_length=400)
    pr_id: int | None = Field(default=None, ge=1)
    is_private: bool | None = None
    diff: str = Field(max_length=5_000_000)


def resolve_scanned_repo(conn: sqlite3.Connection, ref: PullRequestRef) -> str | None:
    """Scanned repo for a Bitbucket repo: explicit map, then `workspace/slug` (on-demand indexed), then bare slug."""
    mapping = json.loads(os.environ.get("SPECWEFT_REPO_MAP", "{}") or "{}")
    for k in (ref.repo_full_name, ref.repo_slug):
        if k and k in mapping:
            return mapping[k]
    names = {r[0] for r in conn.execute("SELECT name FROM repos")}
    for k in (ref.repo_full_name, ref.repo_slug):
        if k and k in names:
            return k
    return None


def _db_path() -> str | None:
    from .api import app
    return getattr(app.state, "db_path", None)


def _ensure_indexed(conn: sqlite3.Connection, ref: PullRequestRef) -> tuple[str | None, dict | None]:
    """(repo, None) when analysis can run now; (None, status_response) while indexing / on failure."""
    repo = resolve_scanned_repo(conn, ref)
    full = ref.repo_full_name
    if repo is not None:
        if full and repo == full and indexer.is_stale(conn, repo) and not ref.is_private:
            job = indexer.job_status(conn, repo)
            if not job or job["status"] not in ("queued", "running"):
                indexer.request_index(conn, full, _db_path())  # refresh in background; serve current index now
        return repo, None
    if not full:
        raise HTTPException(422, "repo_full_name is required to index an unknown repository")
    if ref.is_private:
        # never cloned: the Forge app reads the repo with its own scope and pushes the files to /forge/upload
        job = indexer.job_status(conn, full)
        if job and job["status"] in ("queued", "running"):
            return None, {"status": "indexing", "repo": full, "job": job, "progress": _progress(job),
                          "message": "SpecWeft is indexing this private repository."}
        if job and job["status"] == "failed":
            return None, {"status": "failed", "repo": full, "error": job["error"]}
        return None, {"status": "needs_upload", "repo": full, "job": job,
                      "message": "Private repository: the SpecWeft app is uploading its files for indexing."}
    try:
        job = indexer.job_status(conn, full)
        if job is None or job["status"] == "done":  # done but missing (e.g. DB reset): index again
            job = indexer.request_index(conn, full, _db_path())
    except indexer.IndexError_ as e:
        raise HTTPException(422, str(e)) from e
    if job["status"] == "failed":
        return None, {"status": "failed", "repo": full, "error": job["error"]}
    return None, {"status": "indexing", "repo": full, "job": job, "progress": _progress(job),
                  "message": "SpecWeft is indexing this repository for the first time. This usually takes under a minute."}


def _progress(job: dict) -> dict:
    """Phase + elapsed seconds for the panel's self-refreshing progress state."""
    from datetime import datetime, timezone
    started = job.get("started_at") or job.get("requested_at")
    elapsed = 0
    if started:
        try:
            elapsed = max(0, int((datetime.now(timezone.utc) - datetime.fromisoformat(started)).total_seconds()))
        except ValueError:
            elapsed = 0
    phase = {"queued": "Waiting for a free indexer", "running": "Cloning and indexing",
             "uploading": "Uploading files"}.get(job.get("status"), "Indexing")
    return {"phase": phase, "elapsed_seconds": elapsed}


def _analyze(conn: sqlite3.Connection, ref: PullRequestRef) -> dict:
    repo, pending = _ensure_indexed(conn, ref)
    if pending is not None:
        return pending
    fds = parse_unified_diff(ref.diff)
    changed = sorted({fd.old_path or fd.new_path for fd in fds if (fd.old_path or fd.new_path)})
    if not changed:
        return {"status": "ready", "repo": repo, "changed_files": [], "recommendations": [], "summary": _summary([])}
    recs = [r.to_dict() for r in rank(conn, repo, changed, ref.diff, limit=MAX_RECS)]
    # files the PR already changes are not "missing"
    recs = [r for r in recs if not (r["related_file"]["repo"] == repo and r["related_file"]["path"] in changed)]
    return {"status": "ready", "repo": repo, "pr_id": ref.pr_id, "changed_files": changed, "recommendations": recs,
            "summary": _summary(recs)}


def _summary(recs: list[dict]) -> dict:
    by = {"high": 0, "medium": 0, "low": 0}
    for r in recs:
        by[r["confidence"]] += 1
    return {"total": len(recs), **by}


@router.post("/analyze-pr")
def analyze_pr(ref: PullRequestRef, _claims: dict = Depends(verify_fit), conn=Depends(get_conn)) -> dict:
    """Used by the PR overview panel."""
    try:
        return _analyze(conn, ref)
    except service.ServiceError as e:
        raise HTTPException(422, str(e)) from e


class PrewarmRef(BaseModel):
    repo_full_name: str = Field(min_length=3, max_length=400)


@router.post("/prewarm")
def prewarm(ref: PrewarmRef, _claims: dict = Depends(verify_fit), conn=Depends(get_conn)) -> dict:
    """Install trigger / settings page: index a public repository before its first PR is opened."""
    try:
        if ref.repo_full_name in {r[0] for r in conn.execute("SELECT name FROM repos")} and                 not indexer.is_stale(conn, ref.repo_full_name):
            return {"repo": ref.repo_full_name, "job": indexer.job_status(conn, ref.repo_full_name), "already_indexed": True}
        return {"repo": ref.repo_full_name, "job": indexer.request_index(conn, ref.repo_full_name, _db_path())}
    except indexer.IndexError_ as e:
        raise HTTPException(422, str(e)) from e


class UploadedFile(BaseModel):
    path: str = Field(min_length=1, max_length=1000)
    content_b64: str = Field(max_length=800_000)


class UploadBatch(BaseModel):
    repo_full_name: str = Field(min_length=3, max_length=400)
    commit: str = Field(min_length=7, max_length=64)
    manifest: list[str] = Field(max_length=indexer.MAX_UPLOAD_FILES + 1)
    files: list[UploadedFile] = Field(default_factory=list, max_length=500)


@router.post("/upload")
def upload(batch: UploadBatch, _claims: dict = Depends(verify_fit), conn=Depends(get_conn)) -> dict:
    """Private repositories: the Forge app sends the file manifest of a commit plus a batch of file contents.

    Call with `files=[]` first to learn which paths are missing; once every manifest path has arrived, the scan is
    queued and `job` reports its progress. Resumable: a partial upload for the same commit is kept between calls.
    """
    import base64
    import binascii
    try:
        files = {f.path: base64.b64decode(f.content_b64, validate=True) for f in batch.files}
    except binascii.Error as e:
        raise HTTPException(422, f"invalid base64 file content: {e}") from e
    if sum(len(v) for v in files.values()) > 4_000_000:
        raise HTTPException(413, "upload batch too large (max 4 MB of file content)")
    try:
        return {"repo": batch.repo_full_name, "commit": batch.commit,
                **indexer.receive_files(conn, batch.repo_full_name, batch.commit, batch.manifest, files, _db_path())}
    except indexer.IndexError_ as e:
        raise HTTPException(422, str(e)) from e


@router.get("/index-status")
def index_status(repo_full_name: str, _claims: dict = Depends(verify_fit), conn=Depends(get_conn)) -> dict:
    job = indexer.job_status(conn, repo_full_name)
    return {"repo": repo_full_name, "job": job}


@router.post("/merge-check")
def merge_check(ref: PullRequestRef, _claims: dict = Depends(verify_fit), conn=Depends(get_conn)) -> dict:
    """Bitbucket merge check: fails only on high-confidence (dual-signal) findings. Returns MergeCheckResponse."""
    res = _analyze(conn, ref)
    if res["status"] != "ready":  # never block merges because SpecWeft is not ready
        why = "repository is being indexed" if res["status"] == "indexing" else res.get("error", "not available")
        return {"success": True, "message": f"SpecWeft: check skipped ({why})."}
    high = [r for r in res["recommendations"] if r["confidence"] == "high"]
    if high:
        files = ", ".join(r["related_file"]["path"] for r in high[:5])
        return {"success": False, "message": f"SpecWeft: {len(high)} file(s) very likely need updating: {files}"}
    s = res["summary"]
    return {"success": True, "message": f"SpecWeft: no high-confidence breaks ({s['medium']} medium, {s['low']} low)."}
