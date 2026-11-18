"""SQL / migration extraction with sqlglot (tables, columns, indexes, constraints)."""
from __future__ import annotations

import logging
import re

import sqlglot
from sqlglot import exp

from ..models import RawToken

log = logging.getLogger(__name__)


def _statements(text: str) -> list[tuple[int, str]]:
    """Split on ';' outside quotes, returning (start_line, sql) pairs so locations stay accurate."""
    out, buf, start, line, quote = [], [], 1, 1, None
    for ch in text:
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"', "`"):
            quote = ch
        elif ch == ";":
            stmt = "".join(buf)
            if stmt.strip():
                out.append((start, stmt))
            buf, start = [], line
            continue
        if ch == "\n":
            line += 1
            if not "".join(buf).strip():
                start = line
        buf.append(ch)
    if "".join(buf).strip():
        out.append((start, "".join(buf)))
    return out


def _find_line(stmt: str, start: int, name: str) -> int:
    rx = re.compile(r"(?<![\w])[\"`\[]?" + re.escape(name) + r"[\"`\]]?(?![\w])", re.I)
    for off, l in enumerate(stmt.splitlines()):
        if rx.search(l):
            return start + off
    return start


def extract_sql(text: str, dialect: str | None = None) -> list[RawToken]:
    lines = text.splitlines()
    out: list[RawToken] = []
    for start, stmt in _statements(text):
        try:
            trees = sqlglot.parse(stmt, read=dialect)
        except sqlglot.errors.ParseError as e:  # partial support: keep going with the next statement
            log.debug("sqlglot could not parse statement at line %d: %s", start, e)
            continue
        for tree in trees:
            if tree is None:
                continue
            seen: set[tuple[str, str]] = set()
            for node in tree.walk():
                kind, name = None, None
                if isinstance(node, exp.Table) and node.name:
                    kind, name = "sql_table", node.name
                elif isinstance(node, exp.ColumnDef) and node.name:
                    kind, name = "sql_column", node.name
                elif isinstance(node, exp.Column) and node.name:
                    kind, name = "sql_column", node.name
                elif isinstance(node, exp.Index) and node.name:
                    kind, name = "sql_index", node.name
                elif isinstance(node, exp.Constraint) and node.name:
                    kind, name = "sql_constraint", node.name
                if kind and name and (kind, name) not in seen:
                    seen.add((kind, name))
                    ln = _find_line(stmt, start, name)
                    out.append(RawToken(name, kind, ln, 0, lines[ln - 1].strip()[:200] if ln <= len(lines) else ""))
    return out
