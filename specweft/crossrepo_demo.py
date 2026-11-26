"""Cross-repo contract demo: one PR in one repo, broken files in *other* repos of the same workspace.

Builds a small three-repo workspace (clearly labelled demo fixtures, written to `data/demo_workspace/`):

* `orders-service`  owns the Orders API (OpenAPI + settings + model), has its own CODEOWNERS and git history.
* `checkout-web`    a TypeScript client that reads `shipping_address_line` from that API.
* `platform-infra`  Kubernetes + Terraform that inject `ORDERS_PAYMENT_WEBHOOK_SECRET` into the service.

The PR (branch `rename-shipping-field` in `orders-service`) renames the field in `api/openapi.yaml` and the env var
in `app/settings.py`. Then three tools are asked which other files need review:

* git co-change: only sees `orders-service` history, so it can only name files inside that repo;
* CODEOWNERS: only reads the changed repo's own CODEOWNERS, so it can only request that repo's owners;
* SpecWeft: follows the renamed tokens across the workspace group and flags the holders in the other repos.
"""
from __future__ import annotations

import fnmatch
import shutil
import subprocess
from pathlib import Path

from . import agreements, cochange, db, scanner, service

GROUP = "acme-shop"

OPENAPI_V1 = """openapi: 3.0.0
info:
  title: Orders API
  version: '1'
paths:
  /api/v1/orders/{order_id}:
    get:
      operationId: getOrder
      responses:
        '200':
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Order'
components:
  schemas:
    Order:
      properties:
        order_id:
          type: integer
        shipping_address_line:
          type: string
"""

SETTINGS_V1 = """import os

ORDERS_PAYMENT_WEBHOOK_SECRET = os.environ["ORDERS_PAYMENT_WEBHOOK_SECRET"]
ORDERS_DB_POOL_SIZE = int(os.environ.get("ORDERS_DB_POOL_SIZE", "5"))
"""

MODEL_V1 = """class Order:
    __tablename__ = "orders"

    def to_api(self) -> dict:
        return {"order_id": self.id, "shipping_address_line": self.shipping_address_line}
"""

REPOS: dict[str, list[tuple[str, dict[str, str]]]] = {
    # each repo: list of commits (message, files) so co-change has real history to learn from
    "orders-service": [
        ("initial orders API", {
            "CODEOWNERS": "*            @acme/orders-team\n/api/        @acme/api-guild\n",
            "api/openapi.yaml": OPENAPI_V1,
            "app/settings.py": SETTINGS_V1,
            "app/models.py": MODEL_V1,
            "app/routes.py": "from .models import Order\n\n\ndef get_order(order_id: int) -> dict:\n"
                             "    return Order.get(order_id).to_api()\n",
            "README.md": "# orders-service\n\nServes `/api/v1/orders/{order_id}`.\n",
        }),
        ("add order_id to model and spec", {
            "api/openapi.yaml": OPENAPI_V1 + "        status:\n          type: string\n",
            "app/models.py": MODEL_V1 + "\n    status = 'new'\n",
        }),
        ("tune pool size", {"app/settings.py": SETTINGS_V1 + "ORDERS_LOG_LEVEL = 'info'\n",
                            "app/routes.py": "from .models import Order\n\n\ndef get_order(order_id: int) -> dict:\n"
                                             "    return Order.get(order_id).to_api()  # v2\n"}),
    ],
    "checkout-web": [
        ("checkout client", {
            "CODEOWNERS": "*            @acme/checkout-team\n",
            "src/api/orders.ts": "export interface Order {\n  order_id: number;\n  shipping_address_line: string;\n}\n\n"
                                 "export async function fetchOrder(id: number): Promise<Order> {\n"
                                 "  const r = await fetch(`/api/v1/orders/${id}`);\n  return r.json();\n}\n",
            "src/components/OrderSummary.tsx": "import { Order } from '../api/orders';\n\n"
                                               "export function OrderSummary({ order }: { order: Order }) {\n"
                                               "  return <p>Ships to {order.shipping_address_line}</p>;\n}\n",
            "package.json": '{"name": "checkout-web", "version": "1.0.0"}\n',
        }),
    ],
    "platform-infra": [
        ("orders deployment", {
            "CODEOWNERS": "*            @acme/platform-team\n",
            "k8s/orders-deployment.yaml": "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: orders-service\n"
                                          "spec:\n  template:\n    spec:\n      containers:\n"
                                          "        - name: orders-service\n          image: acme/orders-service:3.2\n"
                                          "          env:\n            - name: ORDERS_PAYMENT_WEBHOOK_SECRET\n"
                                          "              valueFrom:\n                secretKeyRef:\n"
                                          "                  name: orders-secrets\n                  key: webhook\n",
            "terraform/orders.tf": 'variable "orders_payment_webhook_secret" {\n  sensitive = true\n}\n\n'
                                   'resource "aws_ssm_parameter" "orders_webhook" {\n'
                                   '  name  = "/orders/ORDERS_PAYMENT_WEBHOOK_SECRET"\n  type  = "SecureString"\n'
                                   '  value = var.orders_payment_webhook_secret\n}\n',
        }),
    ],
}

PR_BRANCH = "rename-shipping-field"
PR_FILES = {
    "api/openapi.yaml": OPENAPI_V1.replace("shipping_address_line", "shipping_address") + "        status:\n          type: string\n",
    "app/settings.py": SETTINGS_V1.replace("ORDERS_PAYMENT_WEBHOOK_SECRET", "PAYMENTS_WEBHOOK_SECRET") + "ORDERS_LOG_LEVEL = 'info'\n",
}


def _git(cwd: Path, *args: str) -> str:
    env_args = ["-c", "user.name=SpecWeft Demo", "-c", "user.email=demo@specweft.invalid", "-c", "commit.gpgsign=false",
                "-c", "core.autocrlf=false"]
    return subprocess.run(["git", *env_args, *args], cwd=cwd, check=True, capture_output=True, text=True).stdout


def build_workspace(base: Path) -> dict[str, Path]:
    if base.exists():
        shutil.rmtree(base, onerror=lambda f, p, _: (Path(p).chmod(0o700), f(p)))
    roots = {}
    for name, commits in REPOS.items():
        root = base / name
        root.mkdir(parents=True)
        _git(root, "init", "-q", "-b", "main")
        for msg, files in commits:
            for rel, text in files.items():
                p = root / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8", newline="\n")
            _git(root, "add", "-A")
            _git(root, "commit", "-q", "-m", msg)
        roots[name] = root
    o = roots["orders-service"]
    _git(o, "checkout", "-q", "-b", PR_BRANCH)
    for rel, text in PR_FILES.items():
        (o / rel).write_text(text, encoding="utf-8", newline="\n")
    _git(o, "commit", "-q", "-am", "Rename shipping_address_line -> shipping_address; PAYMENTS_WEBHOOK_SECRET")
    _git(o, "checkout", "-q", "main")
    return roots


def codeowners_for(root: Path, paths: list[str]) -> list[str]:
    """GitHub/Bitbucket CODEOWNERS semantics (last matching pattern wins), for files of *this* repo only."""
    rules = []
    for line in (root / "CODEOWNERS").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            pat, *owners = line.split()
            rules.append((pat, owners))
    out: set[str] = set()
    for p in paths:
        owners: list[str] = []
        for pat, ow in rules:
            pp = pat.lstrip("/")
            if pat == "*" or fnmatch.fnmatch(p, pp) or (pp.endswith("/") and p.startswith(pp)):
                owners = ow
        out.update(owners)
    return sorted(out)


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
        o = roots["orders-service"]
        diff = _git(o, "diff", "-U3", "main", PR_BRANCH)
        changed = sorted(PR_FILES)
        res = service.analyze(conn, "orders-service", diff, 20)
        recs = res["recommendations"]

        cc = sorted({b for f in changed for b, _ in cochange.predict_db(conn, "orders-service", f, 10)} - set(changed))
        owners = codeowners_for(o, changed)
        cross = [r for r in recs if r["cross_repo"]]
        flagged = [{"repo": r["related_file"]["repo"], "path": r["related_file"]["path"], "cross_repo": r["cross_repo"],
                    "confidence": r["confidence"], "reason": r["reason"],
                    "evidence": [{"token": e["token"], "change": e["change_type"], "renamed_to": e["renamed_to"],
                                  "changed_at": f'{e["changed_site"]["repo"]}:{e["changed_site"]["path"]}:{e["changed_site"]["line"]}',
                                  "still_held_at": f'{e["holder_site"]["repo"]}:{e["holder_site"]["path"]}:{e["holder_site"]["line"]}',
                                  "holder_line": e["holder_site"]["text"]}
                                 for e in r["agreement_evidence"]]} for r in recs]
        missed_owners = sorted({o for r in cross for o in codeowners_for(roots[r["related_file"]["repo"]],
                                                                          [r["related_file"]["path"]])})
        report = {
            "workspace_group": GROUP, "repos": list(roots), "pr": {"repo": "orders-service", "branch": PR_BRANCH,
                                                                   "changed_files": changed},
            "renamed_tokens": sorted({f'{t["norm"]} -> {t["renamed_to"]}' for t in res["token_changes"]
                                      if t["change_type"] == "renamed" and t.get("renamed_to")}),
            "git_cochange": {"files": cc, "other_repos": [], "note": "co-change is per-repository history"},
            "codeowners": {"reviewers_requested": owners, "owners_of_broken_files_not_requested": missed_owners},
            "specweft": {"flagged": flagged, "cross_repo_count": len(cross),
                         "cross_repo_files": [f'{r["related_file"]["repo"]}:{r["related_file"]["path"]}' for r in cross]},
        }
        service.save_report("demo_cross_repo", report)
        return report
    finally:
        conn.close()


def render(rep: dict) -> str:
    L = [f'PR  {rep["pr"]["repo"]}@{rep["pr"]["branch"]}  changes: {", ".join(rep["pr"]["changed_files"])}',
         f'    renamed: {"; ".join(rep["renamed_tokens"])}', "",
         f'git co-change       -> {", ".join(rep["git_cochange"]["files"]) or "(nothing)"}   [orders-service only]',
         f'CODEOWNERS          -> {", ".join(rep["codeowners"]["reviewers_requested"])}   [orders-service only]',
         f'SpecWeft            -> {rep["specweft"]["cross_repo_count"]} file(s) in OTHER repos of workspace {rep["workspace_group"]!r}:']
    for f in rep["specweft"]["flagged"]:
        if not f["cross_repo"]:
            continue
        L.append(f'  X {f["repo"]}:{f["path"]}  [{f["confidence"]}]')
        for e in f["evidence"][:2]:
            to = f' -> {e["renamed_to"]}' if e["renamed_to"] else ""
            L.append(f'      {e["token"]}{to} ({e["change"]}) at {e["changed_at"]}; still at line {e["still_held_at"].rsplit(":", 1)[1]}: {e["holder_line"]}')
    L.append(f'Owners who would never have been asked: {", ".join(rep["codeowners"]["owners_of_broken_files_not_requested"])}')
    return "\n".join(L)
