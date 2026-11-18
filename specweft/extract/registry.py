"""Pick the extractor for a file path and run it."""
from __future__ import annotations

import posixpath

from ..models import RawToken
from . import code, config, contracts, infra, markdown, sql


def classify(path: str, text: str | None = None) -> str | None:
    """Return the extractor name for a repo-relative POSIX path, or None if unsupported."""
    p = path.lower()
    name = posixpath.basename(p)
    ext = posixpath.splitext(name)[1]
    if name == "dockerfile" or name.startswith("dockerfile.") or name.endswith(".dockerfile"):
        return "dockerfile"
    if name == ".env" or name.startswith(".env.") or ext == ".env":
        return "env"
    if ext == ".py":
        return "python"
    if ext in (".ts", ".mts", ".cts"):
        return "typescript"
    if ext == ".tsx":
        return "tsx"
    if ext in (".js", ".mjs", ".cjs", ".jsx"):
        return "tsx"  # the TSX grammar parses plain JS/JSX
    if ext == ".sql":
        return "sql"
    if ext == ".proto":
        return "proto"
    if ext in (".graphql", ".gql", ".graphqls"):
        return "graphql"
    if ext == ".avsc":
        return "avro"
    if ext in (".tf", ".tfvars", ".hcl"):
        return "terraform"
    if ext in (".md", ".markdown"):
        return "markdown"
    if ext == ".toml":
        return "toml"
    if ext in (".yml", ".yaml", ".json"):
        if "/.github/workflows/" in "/" + p or name in (".gitlab-ci.yml", ".gitlab-ci.yaml") or p.startswith(".circleci/"):
            return "ci"
        if name.startswith(("docker-compose", "compose.")) and ext != ".json":
            return "compose"
        if text is not None and contracts.is_openapi(text):
            return "openapi"
        if ext != ".json" and text is not None and infra.is_k8s(text):
            return "k8s"
        if name in ("package-lock.json",) or name.endswith(".lock.json"):
            return None
        return "json" if ext == ".json" else "yaml"
    return None


def extract(path: str, data: bytes) -> tuple[str | None, list[RawToken]]:
    """Run the matching extractor. Raises on malformed input so the scanner can record the failure."""
    text = data.decode("utf-8", "replace")
    kind = classify(path, text)
    if kind is None:
        return None, []
    lines = text.splitlines()
    if kind in ("python", "typescript", "tsx"):
        return kind, code.extract_code(data, kind)
    if kind == "sql":
        return kind, sql.extract_sql(text)
    if kind == "proto":
        return kind, contracts.extract_proto(text)
    if kind == "graphql":
        return kind, contracts.extract_graphql(text)
    if kind == "avro":
        return kind, contracts.extract_avro(text)
    if kind == "openapi":
        return kind, contracts.extract_openapi(text, path.lower().endswith(".json"))
    if kind == "terraform":
        return kind, infra.extract_terraform(text)
    if kind == "k8s":
        return kind, infra.extract_k8s(text)
    if kind == "compose":
        return kind, infra.extract_compose(text)
    if kind == "ci":
        return kind, infra.extract_ci(text)
    if kind == "dockerfile":
        return kind, infra.extract_dockerfile(text)
    if kind == "markdown":
        return kind, markdown.extract_markdown(text)
    if kind == "env":
        return kind, config.extract_env(text)
    if kind == "toml":
        return kind, config.extract_toml(text)
    if kind == "json":
        return kind, config.entries_to_tokens(config.json_entries(text), lines)
    return kind, config.entries_to_tokens(config.tolerant_yaml_entries(text), lines)
