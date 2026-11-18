"""Shared fixtures. The two fixture repos are small, hand-written TEST FIXTURES (clearly not real projects)
that exercise every extractor family and a known cross-repo contract (`PAYMENT_GATEWAY_URL`, `/api/v2/orders/{}`,
`customer_orders`)."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specweft import agreements, db, scanner

BACKEND = {
    "app/settings.py": 'import os\nPAYMENT_GATEWAY_URL = os.environ["PAYMENT_GATEWAY_URL"]\nORDER_TOPIC = "orders.created.v1"\n',
    "app/routes.py": 'from fastapi import APIRouter\nrouter = APIRouter()\n\n@router.get("/api/v2/orders/{order_id}")\n'
                     'def get_order(order_id: int):\n    return {"customer_orders_id": order_id}\n',
    "app/models.py": 'class CustomerOrder:\n    __tablename__ = "customer_orders"\n    shipping_address_line = None\n',
    "migrations/001_init.sql": "CREATE TABLE customer_orders (\n  id INTEGER PRIMARY KEY,\n  shipping_address_line TEXT\n);\n"
                               "CREATE INDEX ix_customer_orders_id ON customer_orders(id);\n",
    "proto/orders.proto": 'syntax = "proto3";\npackage shop.orders;\nservice OrderService {\n'
                          '  rpc GetCustomerOrder(GetCustomerOrderRequest) returns (CustomerOrderReply);\n}\n'
                          'message GetCustomerOrderRequest {\n  int64 order_id = 1;\n  string shipping_address_line = 2;\n}\n',
    "api/openapi.yaml": "openapi: 3.0.0\ninfo:\n  title: Orders\n  version: '1'\npaths:\n  /api/v2/orders/{order_id}:\n"
                        "    get:\n      operationId: getCustomerOrder\ncomponents:\n  schemas:\n    CustomerOrder:\n"
                        "      properties:\n        shipping_address_line:\n          type: string\n",
    "schema.graphql": "type CustomerOrder {\n  shippingAddressLine: String\n}\n",
    "events/order.avsc": json.dumps({"type": "record", "name": "CustomerOrderCreated", "namespace": "shop.events",
                                     "fields": [{"name": "shipping_address_line", "type": "string"}]}, indent=1),
    "deploy/k8s.yaml": "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: orders-backend\nspec:\n  template:\n"
                       "    spec:\n      containers:\n        - name: orders-backend\n          image: shop/orders-backend:1.4\n"
                       "          ports:\n            - containerPort: 8081\n          env:\n"
                       "            - name: PAYMENT_GATEWAY_URL\n              value: https://payments.internal/v1\n",
    "Dockerfile": "FROM python:3.12-slim AS runtime\nENV PAYMENT_GATEWAY_URL=https://payments.internal/v1\nEXPOSE 8081\n",
    "docker-compose.yml": "services:\n  orders-backend:\n    image: shop/orders-backend:1.4\n    environment:\n"
                          "      - PAYMENT_GATEWAY_URL=https://payments.internal/v1\n",
    ".github/workflows/ci.yml": "on: push\njobs:\n  orders-backend-tests:\n    runs-on: ubuntu-latest\n    env:\n"
                                "      PAYMENT_GATEWAY_URL: ${{ secrets.PAYMENT_GATEWAY_URL }}\n    steps:\n      - run: pytest\n",
    "infra/main.tf": 'variable "payment_gateway_url" {}\nresource "aws_sqs_queue" "customer_orders_queue" {\n'
                     '  name = "customer-orders-queue"\n  url  = var.payment_gateway_url\n}\n',
    "config.toml": '[payments]\ngateway_url_env = "PAYMENT_GATEWAY_URL"\n',
    ".env": "PAYMENT_GATEWAY_URL=https://payments.internal/v1\nORDERS_DB_DSN=sqlite:///orders.db\n",
    "README.md": "Set `PAYMENT_GATEWAY_URL` before starting. Orders live in `customer_orders`.\n\n```\nignored_in_fence_token\n```\n",
}

FRONTEND = {
    "src/api.ts": 'export async function getCustomerOrder(id: number) {\n'
                  '  return fetch(`/api/v2/orders/${id}`);\n}\n',
    "src/OrderView.tsx": 'import { getCustomerOrder } from "./api";\n'
                         'export const OrderView = () => <div data-field="shippingAddressLine">order</div>;\n',
    ".env": "PAYMENT_GATEWAY_URL=https://payments.internal/v1\n",
}


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True,
                          env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
                               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
                               "PATH": __import__("os").environ["PATH"], "HOME": str(root),
                               "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")}).stdout


def make_repo(root: Path, files: dict[str, str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init", "-q", "-b", "main")
    for rel, content in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8", newline="\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "init")
    return root


@pytest.fixture()
def repos(tmp_path: Path) -> dict[str, Path]:
    return {"backend": make_repo(tmp_path / "backend", BACKEND), "frontend": make_repo(tmp_path / "frontend", FRONTEND)}


@pytest.fixture()
def conn(tmp_path: Path):
    c = db.connect(str(tmp_path / "t.db"))
    yield c
    c.close()


@pytest.fixture()
def indexed(conn, repos):
    for name, root in repos.items():
        scanner.scan_repo(conn, root, name, group="shop")
    agreements.build_index(conn)
    return conn
