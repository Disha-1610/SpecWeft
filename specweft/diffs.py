"""PR / commit diff analysis: removed tokens, renames, value changes, touched contexts -> agreement candidates."""
from __future__ import annotations

import difflib
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field

from .agreements import holders, repo_group, token_scores
from .models import AgreementEvidence, Location
from .tokens import normalize, specificity

CHANGE_WEIGHTS = {"removed": 1.0, "renamed": 1.0, "value_changed": 0.8, "touched": 0.5}


@dataclass
class Hunk:
    old_start: int
    new_start: int
    header: str
    lines: list[tuple[str, str, int | None, int | None]] = field(default_factory=list)  # (op, text, old_no, new_no)


@dataclass
class FileDiff:
    old_path: str | None
    new_path: str | None
    hunks: list[Hunk] = field(default_factory=list)

    @property
    def path(self) -> str:
        return self.new_path or self.old_path or ""


_DIFF_GIT = re.compile(r"^diff --git a/(.*) b/(.*)$")
_HUNK = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@ ?(.*)$")


def parse_unified_diff(text: str) -> list[FileDiff]:
    """Parse `git diff`/`git show` output or a plain unified diff.

    Hunk bodies are consumed by the counts in the `@@` header, so content lines that look like
    headers (e.g. a removed line `-- foo` rendered as `--- foo`) are handled correctly."""
    files: list[FileDiff] = []
    cur: FileDiff | None = None
    hunk: Hunk | None = None
    old_left = new_left = 0
    old_no = new_no = 0
    for raw in text.splitlines():
        if hunk is not None and (old_left > 0 or new_left > 0):
            if raw.startswith("\\"):
                continue
            op, body = (raw[0], raw[1:]) if raw else (" ", "")
            if op == "-":
                hunk.lines.append(("-", body, old_no, None)); old_no += 1; old_left -= 1
            elif op == "+":
                hunk.lines.append(("+", body, None, new_no)); new_no += 1; new_left -= 1
            elif op == " ":
                hunk.lines.append((" ", body, old_no, new_no)); old_no += 1; new_no += 1; old_left -= 1; new_left -= 1
            else:  # malformed: abandon hunk
                hunk, old_left, new_left = None, 0, 0
            continue
        hunk = None
        if m := _DIFF_GIT.match(raw):
            cur = FileDiff(m.group(1), m.group(2)); files.append(cur)
        elif raw.startswith("--- "):
            p = raw[4:].strip().split("\t")[0]
            if cur is None or cur.hunks:
                cur = FileDiff(None, None); files.append(cur)
            cur.old_path = None if p == "/dev/null" else re.sub(r"^a/", "", p)
        elif raw.startswith("+++ ") and cur is not None:
            p = raw[4:].strip().split("\t")[0]
            cur.new_path = None if p == "/dev/null" else re.sub(r"^b/", "", p)
        elif raw.startswith("rename from ") and cur is not None:
            cur.old_path = raw[len("rename from "):]
        elif raw.startswith("rename to ") and cur is not None:
            cur.new_path = raw[len("rename to "):]
        elif (m := _HUNK.match(raw)) and cur is not None:
            hunk = Hunk(int(m.group(1)), int(m.group(3)), m.group(5)); cur.hunks.append(hunk)
            old_no, new_no = hunk.old_start, hunk.new_start
            old_left = int(m.group(2)) if m.group(2) is not None else 1
            new_left = int(m.group(4)) if m.group(4) is not None else 1
    return [f for f in files if f.old_path or f.new_path]


_LEX = re.compile(r"""(?P<q>"[^"\n]{1,160}"|'[^'\n]{1,160}'|`[^`\n]{1,160}`)|(?P<p>/[\w{}:.$\-]+(?:/[\w{}:.$\-]*)+)|(?P<i>[A-Za-z_$][\w$]*(?:[.\-][A-Za-z_$][\w$]*)*)|(?P<n>\b\d{4,}\b)""")
_KV = re.compile(r"""^\s*-?\s*["']?([\w.\-/]+)["']?\s*(?::|=|\s)\s*(.+?)\s*,?\s*$""")


def lex_line(text: str) -> list[tuple[str, str]]:
    """Lexical tokens of a single source line -> [(raw, norm)] in order (only specific tokens)."""
    out = []
    for m in _LEX.finditer(text):
        raw = m.group(0)
        if m.group("q"):
            raw = raw[1:-1]
        nt = normalize(raw)
        if nt is not None and specificity(nt) > 0:
            out.append((raw, nt.norm))
        if m.group("i") and ("." in raw or "-" in raw):  # also the parts of dotted names
            for part in re.split(r"[.\-]", raw):
                pt = normalize(part)
                if pt is not None and specificity(pt) > 0 and pt.norm != (nt.norm if nt else None):
                    out.append((part, pt.norm))
    return out


@dataclass
class TokenChange:
    norm: str
    change_type: str           # removed | renamed | value_changed | touched
    path: str
    line: int | None           # line in the OLD file (or new for touched-only)
    raw: str
    renamed_to: str | None = None
    old_value: str | None = None
    new_value: str | None = None


def _pair_lines(removed: list[tuple[str, int | None]], added: list[tuple[str, int | None]]) -> list[tuple[int, int]]:
    pairs, used = [], set()
    for i, (rt, _) in enumerate(removed):
        best, best_j = 0.0, -1
        for j, (at, _) in enumerate(added):
            if j in used:
                continue
            r = difflib.SequenceMatcher(None, rt.strip(), at.strip()).ratio()
            if r > best:
                best, best_j = r, j
        if best >= 0.5:
            used.add(best_j)
            pairs.append((i, best_j))
    return pairs


def detect_changes(fd: FileDiff, indexed_lines: dict[int, list[tuple[str, str]]] | None = None) -> list[TokenChange]:
    """Token-level changes of one file. `indexed_lines` (old line -> [(raw, norm)]) adds extractor-precise tokens."""
    changes: dict[tuple[str, str], TokenChange] = {}
    path = fd.old_path or fd.new_path or ""

    def add(tc: TokenChange) -> None:
        key = (tc.norm, tc.change_type)
        if key not in changes:
            changes[key] = tc

    if fd.new_path is None:  # deleted file: everything it held is removed
        for h in fd.hunks:
            for op, text, old_no, _ in h.lines:
                for raw, norm in _tokens(text, old_no, indexed_lines):
                    add(TokenChange(norm, "removed", path, old_no, raw))
        return list(changes.values())

    for h in fd.hunks:
        blocks: list[tuple[list, list]] = []
        rem, add_ = [], []
        for op, text, old_no, new_no in h.lines + [(" ", "", None, None)]:
            if op == "-":
                rem.append((text, old_no))
            elif op == "+":
                add_.append((text, new_no))
            else:
                if rem or add_:
                    blocks.append((rem, add_))
                rem, add_ = [], []
        all_added_norms = {n for _, a in blocks for t, _ in a for _, n in lex_line(t)}
        for rem, add_ in blocks:
            for i, j in _pair_lines(rem, add_):
                rt, rno = rem[i]
                at, _ = add_[j]
                # value change: same key, different value
                mr, ma = _KV.match(rt), _KV.match(at)
                if mr and ma and normalize(mr.group(1)) and normalize(mr.group(1)) == normalize(ma.group(1)) \
                        and mr.group(2).strip() != ma.group(2).strip():
                    key_n = normalize(mr.group(1))
                    old_v, new_v = mr.group(2).strip().strip("'\","), ma.group(2).strip().strip("'\",")
                    for raw, norm in lex_line(old_v) or []:
                        if norm not in {n for _, n in lex_line(new_v)}:
                            add(TokenChange(norm, "value_changed", path, rno, raw, old_value=old_v, new_value=new_v))
                    if key_n and specificity(key_n) > 0:
                        add(TokenChange(key_n.norm, "value_changed", path, rno, mr.group(1), old_value=old_v, new_value=new_v))
                # renames: aligned single-token replacements
                rtoks, atoks = lex_line(rt), lex_line(at)
                sm = difflib.SequenceMatcher(None, [n for _, n in rtoks], [n for _, n in atoks], autojunk=False)
                for tag, i1, i2, j1, j2 in sm.get_opcodes():
                    if tag == "replace" and (i2 - i1) == (j2 - j1):
                        for k in range(i2 - i1):
                            old_raw, old_n = rtoks[i1 + k]
                            new_raw, new_n = atoks[j1 + k]
                            if old_n != new_n:
                                add(TokenChange(old_n, "renamed", path, rno, old_raw, renamed_to=new_raw))
            for text, old_no in rem:
                for raw, norm in _tokens(text, old_no, indexed_lines):
                    if norm not in all_added_norms:
                        add(TokenChange(norm, "removed", path, old_no, raw))
                    else:
                        add(TokenChange(norm, "touched", path, old_no, raw))
        # enclosing definition of the hunk (`@@ ... @@ class UserCreate(...)`) is touched by the edit
        for raw, norm in lex_line(h.header):
            add(TokenChange(norm, "touched", path, h.old_start, raw))
        for op, text, _, new_no in h.lines:
            if op == "+":
                for raw, norm in lex_line(text):
                    add(TokenChange(norm, "touched", path, new_no, raw))
    # a token that is removed/renamed is not additionally "touched"
    strong = {n for (n, t) in changes if t != "touched"}
    return [c for (n, t), c in changes.items() if t != "touched" or n not in strong]


def _tokens(text: str, old_no: int | None, indexed_lines: dict[int, list[tuple[str, str]]] | None) -> list[tuple[str, str]]:
    toks = lex_line(text)
    if indexed_lines and old_no in indexed_lines:
        seen = {n for _, n in toks}
        toks += [t for t in indexed_lines[old_no] if t[1] not in seen]
    return toks


@dataclass
class AgreementCandidate:
    changed_repo: str
    changed_path: str
    repo: str
    path: str
    score: float
    evidence: list[AgreementEvidence]


def analyze_diff(conn: sqlite3.Connection, diff_text: str, repo: str, max_holders_per_token: int = 60,
                 skip_files_in_diff: bool = True) -> tuple[list[AgreementCandidate], list[TokenChange]]:
    """Diff -> token changes -> holders in the agreement index -> per related-file candidates."""
    fds = parse_unified_diff(diff_text)
    in_diff = {(repo, p) for fd in fds for p in (fd.old_path, fd.new_path) if p}
    group = repo_group(conn, repo)
    all_changes: list[TokenChange] = []
    by_pair: dict[tuple[str, str, str], list[tuple[float, AgreementEvidence]]] = defaultdict(list)
    for fd in fds:
        idx = _indexed_lines(conn, repo, fd.old_path) if fd.old_path else None
        changes = detect_changes(fd, idx)
        all_changes += changes
        scores = token_scores(conn, list({c.norm for c in changes}))
        for c in changes:
            s = scores.get(c.norm)
            if not s:
                continue
            hs = holders(conn, c.norm, limit=max_holders_per_token + 20, group=group)
            for h in hs:
                if (h.repo, h.path) == (repo, fd.old_path) or (h.repo, h.path) == (repo, fd.new_path):
                    continue
                if skip_files_in_diff and (h.repo, h.path) in in_diff:
                    continue
                ev = AgreementEvidence(
                    token=c.norm, change_type=c.change_type, token_score=round(s, 4),
                    changed_site=Location(repo, fd.path, c.line, c.raw),
                    holder_site=Location(h.repo, h.path, h.line, h.context or h.token_raw),
                    renamed_to=c.renamed_to, old_value=c.old_value, new_value=c.new_value)
                by_pair[(fd.path, h.repo, h.path)].append((s * CHANGE_WEIGHTS[c.change_type], ev))
    out = []
    for (cpath, hrepo, hpath), items in by_pair.items():
        best: dict[str, tuple[float, AgreementEvidence]] = {}
        for w, ev in items:  # one evidence per token (strongest)
            if ev.token not in best or w > best[ev.token][0]:
                best[ev.token] = (w, ev)
        prod = 1.0
        for w, _ in best.values():
            prod *= (1 - min(w, 0.99))
        evs = [ev for _, ev in sorted(best.values(), key=lambda x: -x[0])][:5]
        out.append(AgreementCandidate(repo, cpath, hrepo, hpath, 1 - prod, evs))
    out.sort(key=lambda c: -c.score)
    return out, all_changes


def _indexed_lines(conn: sqlite3.Connection, repo: str, path: str) -> dict[int, list[tuple[str, str]]]:
    res: dict[int, list[tuple[str, str]]] = defaultdict(list)
    for r in conn.execute(
            "SELECT o.line, o.token_raw, o.token_norm FROM occurrences o JOIN files f ON f.id=o.file_id"
            " JOIN repos r ON r.id=f.repo_id WHERE r.name=? AND f.path=?", (repo, path)):
        res[r[0]].append((r[1], r[2]))
    return res
