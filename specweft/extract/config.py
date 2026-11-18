"""YAML / JSON / TOML / .env extraction with line numbers.

The walkers yield `Entry(keypath, key, value, line)`; semantic taggers (OpenAPI, Kubernetes, compose, CI, Avro)
in `contracts.py` / `infra.py` turn entries into typed tokens.
"""
from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass
from typing import Any, Callable, Iterator

import yaml

from ..models import RawToken


@dataclass(frozen=True)
class Entry:
    keypath: tuple[str, ...]   # keys from document root to this entry (list indices as "[]")
    key: str | None            # mapping key, None for list items / document scalars
    value: str | None          # scalar value (stringified), None for containers
    line: int                  # 1-based
    doc: int = 0               # document index (multi-doc YAML)


class _Loader(yaml.SafeLoader):
    pass


def yaml_entries(text: str) -> Iterator[Entry]:
    """Walk YAML composition nodes, which carry line marks. Raises yaml.YAMLError on malformed input."""
    for di, root in enumerate(yaml.compose_all(text, Loader=_Loader)):
        if root is None:
            continue
        yield from _walk_node(root, (), di)


def _walk_node(node: yaml.Node, path: tuple[str, ...], doc: int) -> Iterator[Entry]:
    if isinstance(node, yaml.MappingNode):
        for k, v in node.value:
            key = str(k.value) if isinstance(k, yaml.ScalarNode) else "?"
            if isinstance(v, yaml.ScalarNode):
                yield Entry(path + (key,), key, _scalar(v), k.start_mark.line + 1, doc)
            else:
                yield Entry(path + (key,), key, None, k.start_mark.line + 1, doc)
                yield from _walk_node(v, path + (key,), doc)
    elif isinstance(node, yaml.SequenceNode):
        for item in node.value:
            if isinstance(item, yaml.ScalarNode):
                yield Entry(path + ("[]",), None, _scalar(item), item.start_mark.line + 1, doc)
            else:
                yield from _walk_node(item, path + ("[]",), doc)
    elif isinstance(node, yaml.ScalarNode):
        yield Entry(path, None, _scalar(node), node.start_mark.line + 1, doc)


def _scalar(n: yaml.ScalarNode) -> str | None:
    v = n.value
    return None if v is None or v == "" else str(v)


_HELM_LINE = re.compile(r"^\s*\{\{.*\}\}\s*$")
_HELM_INLINE = re.compile(r"\{\{-?.*?-?\}\}")


def tolerant_yaml_entries(text: str) -> list[Entry]:
    """YAML entries; Helm/Jinja templates are de-templated (line numbers preserved) before a retry."""
    try:
        return list(yaml_entries(text))
    except yaml.YAMLError:
        if "{{" not in text:
            raise
    lines = ["" if _HELM_LINE.match(l) else _HELM_INLINE.sub("TEMPLATED", l) for l in text.splitlines()]
    return list(yaml_entries("\n".join(lines)))


def _strip_jsonc(text: str) -> str:
    """Remove // and /* */ comments (outside strings) and trailing commas, keeping newlines."""
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        ch = text[i]
        if in_str:
            out.append(ch)
            if ch == "\\" and i + 1 < n:
                out.append(text[i + 1]); i += 2; continue
            if ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True; out.append(ch)
        elif text.startswith("//", i):
            while i < n and text[i] != "\n":
                i += 1
            continue
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append("\n" * text.count("\n", i, j)); i = j; continue
        else:
            out.append(ch)
        i += 1
    return re.sub(r",(\s*[}\]])", r"\1", "".join(out))


def json_entries(text: str) -> Iterator[Entry]:
    try:
        entries = list(yaml_entries(text))  # JSON is (almost always) valid YAML and gives us line numbers
    except yaml.YAMLError:
        cleaned = _strip_jsonc(text)       # JSONC (tsconfig, VS Code settings)
        try:
            entries = list(yaml_entries(cleaned))
        except yaml.YAMLError:
            data = json.loads(cleaned)       # last resort: correct values, lines located by search
            entries = list(_located(_walk_py(data, ()), text))
    yield from entries


def toml_entries(text: str) -> Iterator[Entry]:
    data = tomllib.loads(text)
    yield from _located(_walk_py(data, ()), text)


def _walk_py(obj: Any, path: tuple[str, ...]) -> Iterator[tuple[tuple[str, ...], str | None, str | None]]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                yield path + (str(k),), str(k), None
                yield from _walk_py(v, path + (str(k),))
            else:
                yield path + (str(k),), str(k), None if v is None else str(v)
    elif isinstance(obj, list):
        for v in obj:
            if isinstance(v, (dict, list)):
                yield from _walk_py(v, path + ("[]",))
            else:
                yield path + ("[]",), None, None if v is None else str(v)


def _located(items: Iterator[tuple[tuple[str, ...], str | None, str | None]], text: str) -> Iterator[Entry]:
    lines = text.splitlines()
    cursor = 0
    for keypath, key, value in items:
        needle = key if key is not None else value
        line = cursor
        if needle:
            for i in range(cursor, len(lines)):
                if needle in lines[i]:
                    line = i
                    break
            else:
                line = next((i for i, l in enumerate(lines) if needle in l), cursor)
        cursor = line
        yield Entry(keypath, key, value, line + 1)


_ENV_LINE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_.]*)\s*=\s*(.*?)\s*$")


def env_entries(text: str) -> Iterator[Entry]:
    for i, line in enumerate(text.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        m = _ENV_LINE.match(line)
        if m:
            val = m.group(2).strip().strip("'\"") or None
            yield Entry((m.group(1),), m.group(1), val, i)


Tagger = Callable[[Entry], tuple[str, str] | None]  # returns (key_kind, value_kind) override


def entries_to_tokens(entries: Iterator[Entry], lines: list[str], tagger: Tagger | None = None,
                      default_key_kind: str = "config_key", default_value_kind: str = "config_value") -> list[RawToken]:
    out: list[RawToken] = []
    for e in entries:
        kk, vk = default_key_kind, default_value_kind
        if tagger:
            tagged = tagger(e)
            if tagged:
                kk, vk = tagged
        ctx = lines[e.line - 1].strip()[:200] if 0 < e.line <= len(lines) else ""
        if e.key is not None and kk:
            out.append(RawToken(e.key, kk, e.line, 0, ctx))
        if e.value is not None and vk:
            for piece in _value_pieces(e.value):
                out.append(RawToken(piece, vk, e.line, 0, ctx))
    return out


_REF = re.compile(r"\$\{\{?\s*([\w.\-]+)\s*\}?\}|\$\(([\w.\-]+)\)|\$([A-Z_][A-Z0-9_]+)")


def _value_pieces(value: str) -> list[str]:
    """A value plus any env/secret references inside it (`${FOO}`, `${{ secrets.FOO }}`, `$FOO`)."""
    pieces = [value] if len(value) <= 160 else []
    for m in _REF.finditer(value):
        ref = next(g for g in m.groups() if g)
        pieces.append(ref.split(".")[-1] if ref.startswith(("secrets.", "env.", "vars.")) else ref)
    return pieces


def extract_env(text: str) -> list[RawToken]:
    lines = text.splitlines()
    return entries_to_tokens(env_entries(text), lines, default_key_kind="env_var", default_value_kind="config_value")


def extract_toml(text: str) -> list[RawToken]:
    return entries_to_tokens(toml_entries(text), text.splitlines())
