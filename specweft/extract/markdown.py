"""Markdown inline-code extraction (fenced blocks are skipped)."""
from __future__ import annotations

import re

from ..models import RawToken

_INLINE = re.compile(r"(?<!`)`([^`\n]+)`(?!`)")
_FENCE = re.compile(r"^\s*(```|~~~)")


def extract_markdown(text: str) -> list[RawToken]:
    out: list[RawToken] = []
    in_fence = False
    for i, line in enumerate(text.splitlines(), start=1):
        if _FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for m in _INLINE.finditer(line):
            out.append(RawToken(m.group(1).strip(), "md_inline_code", i, m.start(1), line.strip()[:200]))
    return out
