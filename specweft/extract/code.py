"""Python and TypeScript/TSX extraction using tree-sitter."""
from __future__ import annotations

import re
from functools import lru_cache

import tree_sitter as ts
import tree_sitter_python as tsp
import tree_sitter_typescript as tst

from ..models import RawToken

_STR_PREFIX = re.compile(r"^[rbufRBUF]*(\"\"\"|'''|\"|'|`)")


@lru_cache(maxsize=None)
def _parser(lang: str) -> ts.Parser:
    if lang == "python":
        language = ts.Language(tsp.language())
    elif lang == "typescript":
        language = ts.Language(tst.language_typescript())
    elif lang == "tsx":
        language = ts.Language(tst.language_tsx())
    else:
        raise ValueError(lang)
    return ts.Parser(language)


def _strip_quotes(text: str) -> str:
    m = _STR_PREFIX.match(text)
    if not m:
        return text
    q = m.group(1)
    body = text[m.end():]
    return body[: -len(q)] if body.endswith(q) else body


# node type -> token kind, per language
_PY_KINDS = {"identifier": "identifier"}
_TS_KINDS = {"identifier": "identifier", "property_identifier": "property", "type_identifier": "type",
             "shorthand_property_identifier": "property", "shorthand_property_identifier_pattern": "property"}
_DEF_PARENTS = {"function_definition", "class_definition", "function_declaration", "class_declaration",
                "method_definition", "interface_declaration", "type_alias_declaration", "enum_declaration"}


def extract_code(source: bytes, lang: str) -> list[RawToken]:
    tree = _parser(lang).parse(source)
    lines = source.decode("utf-8", "replace").splitlines()
    out: list[RawToken] = []
    kinds = _PY_KINDS if lang == "python" else _TS_KINDS
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        t = node.type
        row, col = node.start_point
        if t in ("string", "template_string"):
            # whole literal incl. interpolations (normalized later to `{}`); docstrings contain spaces and are dropped
            if node.start_point[0] == node.end_point[0]:
                text = _strip_quotes(node.text.decode("utf-8", "replace"))
                out.append(RawToken(text, "string", row + 1, col, _ctx(lines, row)))
            continue  # do not descend: identifiers inside f-string interpolations are covered by code elsewhere
        if t in kinds and node.child_count == 0:
            kind = kinds[t]
            if node.parent is not None and node.parent.type in _DEF_PARENTS and node.parent.child_by_field_name("name") == node:
                kind = "definition"
            elif lang == "python" and node.parent is not None and node.parent.type == "attribute" \
                    and node.parent.child_by_field_name("attribute") == node:
                kind = "property"
            out.append(RawToken(node.text.decode("utf-8", "replace"), kind, row + 1, col, _ctx(lines, row)))
        stack.extend(reversed(node.children))
    return out


def _ctx(lines: list[str], row: int) -> str:
    return lines[row].strip()[:200] if 0 <= row < len(lines) else ""
