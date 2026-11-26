""""Forgot to update" incident evaluation.

An incident is a follow-up commit F whose subject says something was left out ("fix missing env var",
"update compose", "sync docs", "forgot to ...") paired with the earlier commit O it repairs. The files F changes
that already existed at O and that O did not touch are the *missed files*. The question for each incident:
had SpecWeft run on O (index + co-change built from history before O, O's own diff as input), would it have
pointed at a missed file — and would plain co-change have?

Pairing O to F, in order of preference:
  1. `curated`  — a hand-verified incident from a JSON file ({"repo", "original", "followup"}).
  2. `pr_ref`   — F's subject names a PR (#123) whose squash/merge commit is found in history.
  3. `token`    — among the ≤ WINDOW_COMMITS earlier commits within WINDOW_DAYS, the one whose changed lines share
                  the most identifier tokens with F's changed lines (≥ MIN_SHARED_TOKENS); no tie-break by recency
                  alone, so an unrelated neighbour commit is never paired.
Every incident records its pairing method and shared tokens so the set can be audited by hand.
"""
from __future__ import annotations

import json
import re
import tempfile
from functools import lru_cache
from pathlib import Path

from . import db, gitutil
from .agreements import build_index
from .cochange import from_history
from .ranker import rank
from .scanner import scan_repo

FOLLOWUP_RX = re.compile(
    r"\b(forg[eo]t|forgotten|missed|missing|was not updated|wasn't updated|not in sync|out of sync|left out|oops)\b"
    r"|\b(sync|syncs|synced|synchroni[sz]e\w*)\b"
    r"|\b(update|updates|updated|fix|fixes|add|adds)\b[^\n]{0,40}\b(compose|docker-compose|\.env|env vars?|"
    r"environment variables?|helm|charts?|manifests?|k8s|kubernetes|kustomiz\w*|openapi|skaffold)\b"
    r"|\balso (update|change|bump|rename|add)\b",
    re.I)
EXCLUDE_RX = re.compile(r"^(revert|merge)\b|\bbump\b.*\bfrom\b.*\bto\b|dependabot|pre-commit autoupdate|"
                        r"(chore|fix)\(deps\)|update (dependency|module)|release notes|^release v|"
                        r"\brelease\b|\bversion\b|^📝 update release notes", re.I)
PR_REF_RX = re.compile(r"#(\d+)")
TOKEN_RX = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")
STOP = {"self", "return", "import", "from", "true", "false", "none", "null", "with", "this", "that", "class",
        "const", "function", "string", "type", "value", "name", "description", "default", "print", "async", "await"}
WINDOW_COMMITS, WINDOW_DAYS, MIN_SHARED_TOKENS = 15, 21, 2
MAX_FILES = 30
TOP_K = 10


@lru_cache(maxsize=4096)
def _changed_tokens(root: str, sha: str) -> frozenset[str]:
    out = gitutil.show_commit(root, sha, unified=0)
    toks: set[str] = set()
    for line in out.splitlines():
        if line[:1] in "+-" and not line.startswith(("+++", "---")):
            toks |= {t for t in TOKEN_RX.findall(line) if t.lower() not in STOP}
    return frozenset(toks)


def mine(root: str | Path, name: str | None = None, curated: list[dict] = ()) -> list[dict]:
    """Candidate incidents from one repository's history (oldest first)."""
    root = str(root)
    name = name or Path(root).name
    hist = gitutil.commits(root, "HEAD")
    pos = {c["sha"]: i for i, c in enumerate(hist)}
    by_prefix = lambda s: next((c for c in hist if c["sha"].startswith(s)), None)
    incidents: list[dict] = []
    for cur in curated:
        if cur.get("repo") not in (name, None):
            continue
        o, f = by_prefix(cur["original"]), by_prefix(cur["followup"])
        if o and f:
            incidents.append(_make(root, name, o, f, "curated", []))
    seen = {i["followup"] for i in incidents}
    for i, f in enumerate(hist):
        if f["sha"] in seen or not FOLLOWUP_RX.search(f["subject"]) or EXCLUDE_RX.search(f["subject"]):
            continue
        if not 1 <= len(f["files"]) <= MAX_FILES:
            continue
        o, method, shared = None, "", []
        m = PR_REF_RX.search(f["subject"])
        if m:
            rx = re.compile(rf"(Merge pull request #{m.group(1)}\b|\(#{m.group(1)}\)\s*$)")
            o = next((c for c in reversed(hist[:i]) if rx.search(c["subject"]) and c["sha"] != f["sha"]), None)
            method = "pr_ref" if o else ""
        if o is None:
            ftoks = _changed_tokens(root, f["sha"])
            best = (0, None, [])
            for c in reversed(hist[max(0, i - WINDOW_COMMITS):i]):
                if f["ts"] - c["ts"] > WINDOW_DAYS * 86400 or not 1 <= len(c["files"]) <= MAX_FILES:
                    continue
                if set(c["files"]) >= set(f["files"]) or EXCLUDE_RX.search(c["subject"]):
                    continue  # O must have left something out
                sh = sorted(t for t in ftoks & _changed_tokens(root, c["sha"]) if len(t) >= 6)
                if len(sh) > best[0]:
                    best = (len(sh), c, sh)
            if best[0] >= MIN_SHARED_TOKENS:
                o, method, shared = best[1], "token", best[2][:10]
        if o is None or pos[o["sha"]] == 0:
            continue
        inc = _make(root, name, o, f, method, shared)
        if inc["missed"] and inc["seeds"]:
            incidents.append(inc)
    return incidents


def _make(root: str, name: str, o: dict, f: dict, method: str, shared: list[str]) -> dict:
    base = gitutil.git(root, "rev-parse", f"{o['sha']}^1").decode().strip()
    at_o = set(gitutil.ls_files(root, o["sha"]))
    old_names = {v: k for k, v in o["renames"].items()}
    seeds = sorted({old_names.get(p, p) for p in o["files"]} & set(gitutil.ls_files(root, base)))
    missed = sorted((set(f["files"]) & at_o) - set(o["files"]))
    return {"repo": name, "original": o["sha"], "original_subject": o["subject"], "followup": f["sha"],
            "followup_subject": f["subject"], "base": base, "ts": o["ts"], "seeds": seeds, "missed": missed,
            "pairing": method, "shared_tokens": shared}


def evaluate(root: str | Path, inc: dict, work_dir: str | Path) -> dict:
    """Run SpecWeft and co-change on the original commit; leakage-free (everything built from `base`)."""
    root = str(root)
    db_path = Path(work_dir) / f"inc_{inc['original'][:10]}.db"
    for s in ("", "-wal", "-shm"):
        Path(str(db_path) + s).unlink(missing_ok=True)
    conn = db.connect(str(db_path))
    try:
        scan_repo(conn, root, inc["repo"], rev=inc["base"], group=inc["repo"])
        build_index(conn)
        cc = from_history(root, inc["base"])
        diff = gitutil.show_commit(root, inc["original"])
        recs = rank(conn, inc["repo"], inc["seeds"], diff, limit=200, now=inc["ts"], use_model=False, cochange=cc)
    finally:
        conn.close()
        for s in ("", "-wal", "-shm"):
            Path(str(db_path) + s).unlink(missing_ok=True)
    missed = set(inc["missed"])
    home = [r for r in recs if r.related_file.repo == inc["repo"]]
    sw_top = [r.related_file.path for r in home[:TOP_K]]
    high = [r.related_file.path for r in home if r.confidence == "high"]
    med_up = [r.related_file.path for r in home if r.confidence in ("high", "medium")]
    agree_only = [r.related_file.path for r in sorted((r for r in home if r.features["agreement"] > 0),
                                                       key=lambda r: -r.features["agreement"])[:TOP_K]]
    co_scores: dict[str, float] = {}
    for s in inc["seeds"]:
        for b, v in cc.predict(s, TOP_K, exclude=set(inc["seeds"])):
            co_scores[b] = max(co_scores.get(b, 0.0), v)
    co_top = [b for b, _ in sorted(co_scores.items(), key=lambda x: (-x[1], x[0]))[:TOP_K]]
    hit = lambda xs: sorted(set(xs) & missed)
    return inc | {"specweft_top10_hits": hit(sw_top), "specweft_high_hits": hit(high), "specweft_high_n": len(high),
                  "specweft_medium_up_hits": hit(med_up), "agreement_top10_hits": hit(agree_only),
                  "cochange_top10_hits": hit(co_top)}


def summarize(results: list[dict]) -> dict:
    n = len(results)
    c = lambda k: sum(1 for r in results if r[k])
    sw, co = c("specweft_top10_hits"), c("cochange_top10_hits")
    sw_not_co = sum(1 for r in results if r["specweft_top10_hits"] and not r["cochange_top10_hits"])
    co_not_sw = sum(1 for r in results if r["cochange_top10_hits"] and not r["specweft_top10_hits"])
    hi_n = sum(r["specweft_high_n"] for r in results)
    return {"incidents": n,
            "caught_specweft_top10": sw, "caught_cochange_top10": co,
            "caught_agreement_only_top10": c("agreement_top10_hits"),
            "caught_specweft_high_tier": c("specweft_high_hits"),
            "caught_specweft_medium_or_high": c("specweft_medium_up_hits"),
            "caught_by_specweft_missed_by_cochange": sw_not_co,
            "caught_by_cochange_missed_by_specweft": co_not_sw,
            "high_tier_flags_total": hi_n,
            "headline": f"caught {sw_not_co} of {n} incidents co-change missed "
                        f"(SpecWeft {sw}/{n}, co-change {co}/{n}, top-{TOP_K})",
            "by_pairing": {m: sum(1 for r in results if r["pairing"] == m) for m in sorted({r["pairing"] for r in results})}}


def run(repos: list[tuple[str, str]], curated_path: str | None = None, max_incidents: int = 50) -> dict:
    curated = json.loads(Path(curated_path).read_text(encoding="utf-8")) if curated_path else []
    results: list[dict] = []
    errors: list[dict] = []
    with tempfile.TemporaryDirectory() as work:
        for root, name in repos:
            for inc in mine(root, name, curated):
                if len(results) >= max_incidents:
                    break
                try:
                    results.append(evaluate(root, inc, work))
                except Exception as e:  # one broken snapshot must not sink the set
                    errors.append({"repo": name, "original": inc["original"], "error": str(e)[:300]})
    return {"summary": summarize(results), "incidents": results, "errors": errors,
            "note": "missed = files the follow-up changed that existed at the original commit and it did not touch; "
                    "index and co-change built from the original commit's parent; audit `pairing`/`shared_tokens`"}
