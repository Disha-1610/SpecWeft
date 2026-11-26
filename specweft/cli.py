"""Command-line interface: `python -m specweft.cli <command>`."""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

from . import agreements, db, evaluation, navigation, scanner, service
from .ranker import train_logistic
from .traces import claude_code
from .traces.ingest import ingest_file

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, default=lambda o: o.__dict__))


def cmd_scan(a, conn) -> None:
    for root in a.roots:
        s = scanner.scan_repo(conn, root, a.name if len(a.roots) == 1 else None, rev=a.rev, exclude=a.exclude or [],
                              group=a.group)
        _print({"repo": s.repo, "files": s.files_extracted, "occurrences": s.occurrences,
                 "failures": len(s.failures), "by_extractor": s.by_extractor})
    if not a.no_index:
        _print(agreements.build_index(conn))


def cmd_index(a, conn) -> None:
    _print(agreements.build_index(conn))


def cmd_ingest(a, conn) -> None:
    paths = [Path(p) for p in a.paths]
    if a.source == "claude_code":
        expanded = []
        for p in paths:
            expanded += claude_code.discover(p) if p.is_dir() else [p]
        paths = expanded
    total = {"sessions": 0, "events": 0, "skipped": 0}
    for p in paths:
        st = ingest_file(conn, a.source, p, repo_root=a.repo_root, repo_name=a.repo_name)
        for k in total:
            total[k] += st[k]
    _print(total)
    if not a.no_navigate:
        _print(navigation.build_navigation(conn))


def cmd_navigate(a, conn) -> None:
    _print(navigation.build_navigation(conn, window=a.window))


def cmd_analyze(a, conn) -> None:
    if a.diff:
        diff = sys.stdin.read() if a.diff == "-" else Path(a.diff).read_text(encoding="utf-8")
    else:
        diff = service.diff_for(conn, a.repo, commit=a.commit)
    _print(service.analyze(conn, a.repo, diff, a.limit))


def cmd_rank(a, conn) -> None:
    diff = Path(a.diff).read_text(encoding="utf-8") if a.diff else None
    _print([r.to_dict() for r in service.rank_files(conn, a.repo, a.files, diff, a.limit)])


def cmd_replay(a, conn) -> None:
    others = [(r, Path(r).name) for r in (a.others or [])]
    res = evaluation.replay(str(DATA / f"replay_{Path(a.root).name}.db"), a.root, a.name, others, a.cutoff,
                            a.max_commits, label_conn=conn, run=a.run or f"replay:{Path(a.root).name}")
    res["lr_holdout"] = evaluation.lr_holdout(conn, a.run or f"replay:{Path(a.root).name}")
    service.save_report(f"replay_{Path(a.root).name}", res)
    _print(res)


def cmd_incidents(a, conn) -> None:
    from . import incidents
    res = incidents.run([(r, Path(r).name) for r in a.roots], a.curated, a.max_incidents)
    service.save_report("incidents", res)
    _print(res["summary"])


def cmd_train(a, conn) -> None:
    _print(train_logistic(conn, a.run))


def cmd_eval_gold(a, conn) -> None:
    rev = a.rev
    if a.pr and a.root:
        pr = evaluation.find_pr(a.root, a.pr)
        if pr is None:
            raise SystemExit(f"PR #{a.pr} not found in {a.root}")
        rev = pr["base"]
    res = evaluation.gold_eval(conn, a.nav_repo, a.scanned_repo, a.root, rev or "HEAD", label_conn=conn)
    service.save_report("gold_" + a.nav_repo.replace("/", "__"), res)
    _print(res)


def cmd_serve(a, conn) -> None:
    from .api import serve
    conn.close()
    serve(a.host, a.port, a.db)


def cmd_pipeline(a, conn) -> None:
    """Complete workflow on the real data in data/ (see README)."""
    repos = DATA / "repos"
    trajs = DATA / "trajectories"
    report: dict = {}
    # 1-4: scan + extract + normalize/score + store
    scans = []
    # full-stack-fastapi-template is built on sqlmodel (library -> consumer contract): one workspace group
    for name, group, excl in (("full-stack-fastapi-template", "fastapi-stack", []),
                              ("sqlmodel", "fastapi-stack", ["docs/*"]),
                              ("microservices-demo", "microservices-demo", [])):
        s = scanner.scan_repo(conn, repos / name, name, group=group, exclude=excl)
        scans.append({"repo": name, "group": group, "files": s.files_extracted, "occurrences": s.occurrences,
                      "failures": len(s.failures), "by_extractor": s.by_extractor})
    cc_root = repos / "cognitive_complexity"
    pr = evaluation.find_pr(cc_root, 15)
    s = scanner.scan_repo(conn, cc_root, "cognitive_complexity", rev=pr["base"])  # code as the agents saw it
    scans.append({"repo": "cognitive_complexity", "rev": pr["base"], "files": s.files_extracted, "occurrences": s.occurrences})
    s = scanner.scan_repo(conn, ROOT, "SpecWeft", exclude=["data/*", "tests/fixtures/*"])
    scans.append({"repo": "SpecWeft", "files": s.files_extracted, "occurrences": s.occurrences})
    report["scan"] = scans
    report["index"] = agreements.build_index(conn)
    # 7-9: traces -> navigation
    ing = {}
    ing["swe_agent"] = ingest_file(conn, "swe_agent", trajs / "sweagent_rows.json")
    ing["openhands"] = ingest_file(conn, "openhands", trajs / "openhands_rows.json")
    cc_sessions = {"sessions": 0, "events": 0}
    projects = Path(a.claude_projects or Path.home() / ".claude" / "projects")
    if projects.is_dir():
        for p in claude_code.discover(projects):
            st = ingest_file(conn, "claude_code", p)
            cc_sessions["sessions"] += st["sessions"]; cc_sessions["events"] += st["events"]
    ing["claude_code"] = cc_sessions
    report["ingest"] = ing
    report["navigation"] = navigation.build_navigation(conn)
    # 13: evaluation (replay + gold), 10-11: LR fusion when labels suffice
    conn.execute("DELETE FROM replay_labels"); conn.commit()
    rep, holdouts = {}, []
    for name, others in (("full-stack-fastapi-template", ["sqlmodel"]), ("microservices-demo", [])):
        r = evaluation.replay(str(DATA / f"replay_{name}.db"), str(repos / name), name,
                              [(str(repos / o), o) for o in others], max_commits=a.max_commits, label_conn=conn,
                              run=f"replay:{name}")
        r["lr_holdout"] = evaluation.lr_holdout(conn, f"replay:{name}")
        if r["lr_holdout"].get("evaluated"):
            holdouts.append(r["lr_holdout"])
        service.save_report(f"replay_{name}", r)
        rep[name] = r["methods"] | {"tier_precision": r["tier_precision"], "lr_holdout": r["lr_holdout"]}
    report["replay"] = rep
    g = evaluation.gold_eval(conn, "Melevir/cognitive_complexity", "cognitive_complexity", str(cc_root), pr["base"],
                             label_conn=conn)
    g_pr = evaluation.gold_eval(conn, "Melevir/cognitive_complexity", "cognitive_complexity", str(cc_root), pr["base"],
                                gold_override=pr["files"])
    service.save_report("gold_cognitive_complexity", g)
    service.save_report("gold_cognitive_complexity_pr_files", g_pr)
    report["gold"] = {"resolved_patch": g["methods"], "upstream_pr": g_pr["methods"], "mode": g["evaluation_mode"]}
    holdout = None
    if holdouts:
        holdout = {"auc_lr": sum(h["auc_lr"] for h in holdouts) / len(holdouts),
                   "auc_weighted": sum(h["auc_weighted"] for h in holdouts) / len(holdouts), "runs": len(holdouts)}
    report["train"] = train_logistic(conn, holdout=holdout or {"auc_lr": 0, "auc_weighted": 1, "runs": 0})
    # 5-6, 12: historical PR demo — index the code as it was before the PR, feed ONLY the seed file's diff,
    # and compare SpecWeft's recommendations with the files the PR actually had to change.
    report["demo_pr"] = demo_pr(str(repos / "full-stack-fastapi-template"), a.demo_commit or "32ab6dd",
                                "backend/app/core/config.py", str(repos / "sqlmodel"))
    service.save_report("pipeline", report)
    _print(report)


def demo_pr(root: str, commit: str, seed: str, related_root: str | None = None) -> dict:
    from . import gitutil
    from .agreements import build_index as _bi
    demo_db = DATA / "demo_pr.db"
    for suf in ("", "-wal", "-shm"):
        Path(str(demo_db) + suf).unlink(missing_ok=True)
    c = db.connect(str(demo_db))
    try:
        parent = gitutil.git(root, "rev-parse", f"{commit}^1").decode().strip()
        name = Path(root).name
        scanner.scan_repo(c, root, name, rev=parent, group="fastapi-stack")
        if related_root:
            ts = gitutil.git(root, "log", "-1", "--format=%ct", parent).decode().strip()
            rrev = gitutil.git(related_root, "rev-list", "-1", f"--before=@{ts}", "HEAD").decode().strip()
            if rrev:
                scanner.scan_repo(c, related_root, Path(related_root).name, rev=rrev, group="fastapi-stack")
        _bi(c)
        diff = gitutil.git(root, "show", "-U3", "-M", "--format=", commit, "--", seed).decode("utf-8", "replace")
        actual = set(gitutil.git(root, "diff", "--name-only", parent, commit).decode().split()) - {seed}
        res = service.analyze(c, name, diff, 10)
        top = [r["related_file"]["path"] for r in res["recommendations"]]
        out = {"commit": commit, "subject": gitutil.git(root, "log", "-1", "--format=%s", commit).decode().strip(),
               "seed": seed, "files_actually_changed_by_pr": sorted(actual),
               "removed_or_renamed_tokens": sorted({t["norm"] for t in res["token_changes"]
                                                    if t["change_type"] in ("removed", "renamed")})[:20],
               "top10": [{"path": p, "hit": p in actual, "confidence": r["confidence"], "score": r["ranking_score"],
                          "reason": r["reason"]} for p, r in zip(top, res["recommendations"])],
               "P@10": round(sum(p in actual for p in top[:10]) / 10, 3),
               "recall@10": round(sum(p in actual for p in top[:10]) / max(1, len(actual)), 3)}
        service.save_report("demo_pr", out | {"recommendations": res["recommendations"]})
        return out
    finally:
        c.close()


def cmd_cross_repo_demo(a, conn) -> None:
    from . import crossrepo_demo
    rep = crossrepo_demo.run(Path(a.workspace), DATA / "demo_cross_repo.db")
    print(json.dumps(rep, indent=2) if a.json else crossrepo_demo.render(rep))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="specweft", description=__doc__)
    p.add_argument("--db", default=None, help="SQLite path (default data/specweft.db or $SPECWEFT_DB)")
    p.add_argument("-v", "--verbose", action="store_true")
    sp = p.add_subparsers(dest="cmd", required=True)

    s = sp.add_parser("scan", help="scan repositories and rebuild the agreement index")
    s.add_argument("roots", nargs="+"); s.add_argument("--name"); s.add_argument("--rev")
    s.add_argument("--group", help="workspace group: repos of one system; cross-repo agreements stay inside a group")
    s.add_argument("--exclude", action="append"); s.add_argument("--no-index", action="store_true")
    s.set_defaults(fn=cmd_scan)
    sp.add_parser("index", help="rebuild agreement index").set_defaults(fn=cmd_index)

    s = sp.add_parser("ingest", help="ingest trajectories")
    s.add_argument("source", choices=["claude_code", "swe_agent", "openhands"]); s.add_argument("paths", nargs="+")
    s.add_argument("--repo-root"); s.add_argument("--repo-name"); s.add_argument("--no-navigate", action="store_true")
    s.set_defaults(fn=cmd_ingest)
    s = sp.add_parser("navigate", help="rebuild navigation edges"); s.add_argument("--window", type=int, default=15)
    s.set_defaults(fn=cmd_navigate)

    s = sp.add_parser("analyze", help="analyze a diff or commit")
    s.add_argument("--repo", required=True); g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--diff", help="diff file or '-' for stdin"); g.add_argument("--commit")
    s.add_argument("--limit", type=int, default=20); s.set_defaults(fn=cmd_analyze)
    s = sp.add_parser("rank", help="rank files affected by changed files")
    s.add_argument("--repo", required=True); s.add_argument("--files", nargs="+", required=True)
    s.add_argument("--diff"); s.add_argument("--limit", type=int, default=20); s.set_defaults(fn=cmd_rank)

    s = sp.add_parser("replay", help="historical replay evaluation")
    s.add_argument("root"); s.add_argument("--name"); s.add_argument("--others", nargs="*")
    s.add_argument("--cutoff"); s.add_argument("--max-commits", type=int, default=150); s.add_argument("--run")
    s.set_defaults(fn=cmd_replay)
    s = sp.add_parser("incidents", help="'forgot to update' incident evaluation vs co-change")
    s.add_argument("roots", nargs="+"); s.add_argument("--curated", help="JSON list of {repo, original, followup}")
    s.add_argument("--max-incidents", type=int, default=50); s.set_defaults(fn=cmd_incidents)
    s = sp.add_parser("train", help="train logistic fusion on replay labels (activated unconditionally)"); s.add_argument("--run")
    s.set_defaults(fn=cmd_train)
    s = sp.add_parser("eval-gold", help="gold-patch evaluation of navigation")
    s.add_argument("--nav-repo", required=True); s.add_argument("--scanned-repo"); s.add_argument("--root")
    s.add_argument("--rev"); s.add_argument("--pr", type=int); s.set_defaults(fn=cmd_eval_gold)
    s = sp.add_parser("cross-repo-demo", help="PR in one repo flags files in other repos of the workspace")
    s.add_argument("--workspace", default=str(DATA / "demo_workspace")); s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_cross_repo_demo)
    s = sp.add_parser("serve", help="run the API + web UI")
    s.add_argument("--host", default="127.0.0.1"); s.add_argument("--port", type=int, default=8765)
    s.set_defaults(fn=cmd_serve)
    s = sp.add_parser("pipeline", help="run the complete workflow on data/")
    s.add_argument("--max-commits", type=int, default=120); s.add_argument("--claude-projects")
    s.add_argument("--demo-commit"); s.set_defaults(fn=cmd_pipeline)
    return p


def main(argv: list[str] | None = None) -> int:
    a = build_parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else os.environ.get("SPECWEFT_LOG", "WARNING"),
                        format="%(levelname)s %(name)s: %(message)s")
    conn = db.connect(a.db)
    try:
        a.fn(a, conn)
    except (service.ServiceError, FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    finally:
        try:
            conn.close()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
