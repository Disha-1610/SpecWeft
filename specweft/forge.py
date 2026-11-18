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

from . import service
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
    diff: str = Field(max_length=5_000_000)


def resolve_scanned_repo(conn: sqlite3.Connection, ref: PullRequestRef) -> str:
    mapping = json.loads(os.environ.get("SPECWEFT_REPO_MAP", "{}") or "{}")
    for k in (ref.repo_full_name, ref.repo_slug):
        if k and k in mapping:
            return mapping[k]
    names = {r[0] for r in conn.execute("SELECT name FROM repos")}
    for k in (ref.repo_slug, (ref.repo_full_name or "").split("/")[-1]):
        if k in names:
            return k
    raise HTTPException(404, f"repository '{ref.repo_full_name or ref.repo_slug}' is not indexed by SpecWeft; "
                             f"scan it with `python -m specweft.cli scan <clone> --name {ref.repo_slug}`")


def _analyze(conn: sqlite3.Connection, ref: PullRequestRef) -> dict:
    repo = resolve_scanned_repo(conn, ref)
    fds = parse_unified_diff(ref.diff)
    changed = sorted({fd.old_path or fd.new_path for fd in fds if (fd.old_path or fd.new_path)})
    if not changed:
        return {"repo": repo, "changed_files": [], "recommendations": [], "summary": _summary([])}
    recs = [r.to_dict() for r in rank(conn, repo, changed, ref.diff, limit=MAX_RECS)]
    # files the PR already changes are not "missing"
    recs = [r for r in recs if not (r["related_file"]["repo"] == repo and r["related_file"]["path"] in changed)]
    return {"repo": repo, "pr_id": ref.pr_id, "changed_files": changed, "recommendations": recs,
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


@router.post("/merge-check")
def merge_check(ref: PullRequestRef, _claims: dict = Depends(verify_fit), conn=Depends(get_conn)) -> dict:
    """Bitbucket merge check: fails only on high-confidence (dual-signal) findings. Returns MergeCheckResponse."""
    try:
        res = _analyze(conn, ref)
    except HTTPException as e:
        if e.status_code == 404:  # unindexed repo: never block merges because of SpecWeft itself
            return {"success": True, "message": "SpecWeft: repository not indexed; check skipped."}
        raise
    high = [r for r in res["recommendations"] if r["confidence"] == "high"]
    if high:
        files = ", ".join(r["related_file"]["path"] for r in high[:5])
        return {"success": False, "message": f"SpecWeft: {len(high)} file(s) very likely need updating: {files}"}
    s = res["summary"]
    return {"success": True, "message": f"SpecWeft: no high-confidence breaks ({s['medium']} medium, {s['low']} low)."}
