import pytest
import yaml

from specweft.extract.registry import classify, extract
from tests.conftest import BACKEND, FRONTEND


def toks(path, text):
    kind, out = extract(path, text.encode())
    return kind, {(t.text, t.kind) for t in out}, out


@pytest.mark.parametrize("path,expected", [
    ("app/x.py", "python"), ("src/a.ts", "typescript"), ("src/a.tsx", "tsx"), ("m/001.sql", "sql"),
    ("p/a.proto", "proto"), ("s.graphql", "graphql"), ("e.avsc", "avro"), ("i/main.tf", "terraform"),
    ("Dockerfile", "dockerfile"), (".env", "env"), (".env.prod", "env"), ("README.md", "markdown"),
    ("pyproject.toml", "toml"), (".github/workflows/ci.yml", "ci"), ("docker-compose.yml", "compose"),
    ("x.bin", None)])
def test_classify(path, expected):
    assert classify(path, "") == expected


def test_python_tree_sitter():
    kind, s, out = toks("app/settings.py", BACKEND["app/settings.py"])
    assert kind == "python"
    assert ("PAYMENT_GATEWAY_URL", "string") in s and ("orders.created.v1", "string") in s
    line = next(t.line for t in out if t.text == "PAYMENT_GATEWAY_URL" and t.kind == "string")
    assert line == 2
    _, s, _ = toks("app/models.py", BACKEND["app/models.py"])
    assert ("CustomerOrder", "definition") in s


def test_typescript_template_string():
    _, s, _ = toks("src/api.ts", FRONTEND["src/api.ts"])
    assert ("/api/v2/orders/${id}", "string") in s
    assert ("getCustomerOrder", "definition") in s


def test_sql_sqlglot():
    _, s, out = toks("migrations/001_init.sql", BACKEND["migrations/001_init.sql"])
    assert ("customer_orders", "sql_table") in s and ("shipping_address_line", "sql_column") in s
    assert next(t.line for t in out if t.text == "shipping_address_line") == 3


def test_contracts():
    _, s, _ = toks("api/openapi.yaml", BACKEND["api/openapi.yaml"])
    assert ("/api/v2/orders/{order_id}", "route") in s and ("getCustomerOrder", "operation_id") in s
    assert ("CustomerOrder", "schema") in s and ("shipping_address_line", "field") in s
    _, s, _ = toks("proto/orders.proto", BACKEND["proto/orders.proto"])
    assert {("GetCustomerOrder", "proto_rpc"), ("shipping_address_line", "proto_field"), ("shop.orders", "proto_package")} <= s
    _, s, _ = toks("schema.graphql", BACKEND["schema.graphql"])
    assert ("shippingAddressLine", "graphql_field") in s
    _, s, _ = toks("events/order.avsc", BACKEND["events/order.avsc"])
    assert ("shipping_address_line", "avro_name") in s


def test_infra():
    _, s, _ = toks("deploy/k8s.yaml", BACKEND["deploy/k8s.yaml"])
    assert {("PAYMENT_GATEWAY_URL", "env_var"), ("8081", "port"), ("orders-backend", "k8s_name")} <= s
    _, s, _ = toks("Dockerfile", BACKEND["Dockerfile"])
    assert {("PAYMENT_GATEWAY_URL", "env_var"), ("8081", "port"), ("runtime", "docker_stage")} <= s
    _, s, _ = toks("docker-compose.yml", BACKEND["docker-compose.yml"])
    assert ("PAYMENT_GATEWAY_URL", "env_var") in s and ("orders-backend", "service") in s
    _, s, _ = toks(".github/workflows/ci.yml", BACKEND[".github/workflows/ci.yml"])
    assert ("PAYMENT_GATEWAY_URL", "env_var") in s and ("orders-backend-tests", "ci_job") in s
    assert ("runs-on", "config_key") not in s  # schema vocabulary is not an agreement
    _, s, _ = toks("infra/main.tf", BACKEND["infra/main.tf"])
    assert {("payment_gateway_url", "tf_variable"), ("customer_orders_queue", "tf_resource_name"),
            ("aws_sqs_queue", "tf_resource_type")} <= s


def test_config_env_toml_markdown():
    _, s, _ = toks(".env", BACKEND[".env"])
    assert ("ORDERS_DB_DSN", "env_var") in s
    _, s, _ = toks("config.toml", BACKEND["config.toml"])
    assert ("PAYMENT_GATEWAY_URL", "config_value") in s
    _, s, _ = toks("README.md", BACKEND["README.md"])
    assert ("customer_orders", "md_inline_code") in s
    assert not any(t == "ignored_in_fence_token" for t, _ in s)


def test_helm_template_and_jsonc_are_tolerated():
    helm = "apiVersion: v1\nkind: Service\n{{- if .Values.x }}\nmetadata:\n  name: {{ .Values.name }}-svc\n{{- end }}\n"
    kind, out = extract("charts/t/svc.yaml", helm.encode())
    assert kind == "k8s" and any(t.kind == "k8s_name" for t in out)
    jsonc = '{\n  // comment\n  "compilerOptions": { "strictNullChecks": true, },\n}\n'
    kind, out = extract("tsconfig.json", jsonc.encode())
    assert any(t.text == "strictNullChecks" and t.line == 3 for t in out)


def test_malformed_raises_for_scanner_to_record():
    with pytest.raises(yaml.YAMLError):
        extract("bad.yaml", b"a: [1, 2\nb: : :")
