"""API contract extraction: OpenAPI (YAML/JSON), Protocol Buffers, GraphQL SDL, Avro schemas."""
from __future__ import annotations

import json
import re

from ..models import RawToken
from .config import Entry, entries_to_tokens, json_entries, yaml_entries

HTTP_METHODS = {"get", "put", "post", "delete", "patch", "options", "head", "trace"}


def is_openapi(text: str) -> bool:
    head = text[:4000]
    return bool(re.search(r"""^\s*["']?(openapi|swagger)["']?\s*:""", head, re.M))


def _openapi_tagger(e: Entry) -> tuple[str, str] | None:
    kp = e.keypath
    if len(kp) == 2 and kp[0] == "paths":
        return ("route", "")
    if e.key == "operationId":
        return ("", "operation_id")
    if len(kp) == 3 and kp[0] == "components" and kp[1] == "schemas":
        return ("schema", "")
    if len(kp) == 2 and kp[0] == "definitions":
        return ("schema", "")
    if len(kp) >= 2 and kp[-2] == "properties":
        return ("field", "")
    if e.key == "$ref":
        return ("", "schema_ref")
    if e.key in ("name",) and "parameters" in kp:
        return ("", "parameter")
    if e.key in HTTP_METHODS and len(kp) == 3 and kp[0] == "paths":
        return ("", "")
    if e.key in ("description", "summary", "title"):
        return ("", "")
    return None


def extract_openapi(text: str, is_json: bool) -> list[RawToken]:
    entries = json_entries(text) if is_json else yaml_entries(text)
    toks = entries_to_tokens(entries, text.splitlines(), _openapi_tagger, default_key_kind="", default_value_kind="")
    # `#/components/schemas/Foo` -> `Foo`
    return [RawToken(t.text.rsplit("/", 1)[-1], "schema", t.line, t.col, t.context) if t.kind == "schema_ref" else t
            for t in toks]


_PROTO_RULES = [
    (re.compile(r"^\s*package\s+([\w.]+)\s*;"), "proto_package"),
    (re.compile(r"^\s*message\s+(\w+)"), "proto_message"),
    (re.compile(r"^\s*enum\s+(\w+)"), "proto_enum"),
    (re.compile(r"^\s*service\s+(\w+)"), "proto_service"),
    (re.compile(r"^\s*(?:optional\s+|repeated\s+|required\s+)?(?:map<[^>]+>|[\w.]+)\s+(\w+)\s*=\s*\d+"), "proto_field"),
    (re.compile(r"^\s*([A-Z][A-Z0-9_]+)\s*=\s*\d+\s*;"), "proto_enum_value"),
]
_RPC = re.compile(r"^\s*rpc\s+(\w+)\s*\(\s*(?:stream\s+)?([\w.]+)\s*\)\s*returns\s*\(\s*(?:stream\s+)?([\w.]+)\s*\)")


def extract_proto(text: str) -> list[RawToken]:
    out: list[RawToken] = []
    for i, line in enumerate(text.splitlines(), start=1):
        code = line.split("//", 1)[0]
        m = _RPC.match(code)
        if m:
            out.append(RawToken(m.group(1), "proto_rpc", i, m.start(1), line.strip()))
            out.append(RawToken(m.group(2).split(".")[-1], "proto_message", i, m.start(2), line.strip()))
            out.append(RawToken(m.group(3).split(".")[-1], "proto_message", i, m.start(3), line.strip()))
            continue
        for rx, kind in _PROTO_RULES:
            m = rx.match(code)
            if m:
                out.append(RawToken(m.group(1), kind, i, m.start(1), line.strip()))
                break
    return out


_GQL_TYPE = re.compile(r"^\s*(?:extend\s+)?(type|input|enum|interface|union|scalar)\s+(\w+)")
_GQL_FIELD = re.compile(r"^\s*(\w+)\s*(?:\([^)]*\))?\s*:\s*\[?\s*(\w+)")
_GQL_OP = re.compile(r"^\s*(query|mutation|subscription|fragment)\s+(\w+)")


def extract_graphql(text: str) -> list[RawToken]:
    out: list[RawToken] = []
    for i, line in enumerate(text.splitlines(), start=1):
        code = line.split("#", 1)[0]
        if m := _GQL_TYPE.match(code):
            out.append(RawToken(m.group(2), f"graphql_{m.group(1)}", i, m.start(2), line.strip()))
        elif m := _GQL_OP.match(code):
            out.append(RawToken(m.group(2), "graphql_operation", i, m.start(2), line.strip()))
        elif m := _GQL_FIELD.match(code):
            out.append(RawToken(m.group(1), "graphql_field", i, m.start(1), line.strip()))
            out.append(RawToken(m.group(2), "graphql_type_ref", i, m.start(2), line.strip()))
    return out


def extract_avro(text: str) -> list[RawToken]:
    json.loads(text)  # validate; raises on malformed schema

    def tagger(e: Entry) -> tuple[str, str] | None:
        if e.key in ("name", "namespace", "aliases") or (e.key is None and len(e.keypath) >= 2 and e.keypath[-2] == "aliases"):
            return ("", "avro_name")
        if e.key == "type":
            return ("", "avro_type_ref")
        return ("", "")

    return entries_to_tokens(json_entries(text), text.splitlines(), tagger, default_key_kind="", default_value_kind="")
