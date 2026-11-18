"""Token normalization, version-suffix extraction, template normalization, stoplist and specificity."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

MAX_TOKEN_LEN = 160

STOPWORDS: frozenset[str] = frozenset("""
a an and are as at be by for from has have in is it of on or the to with not no yes this that these those
true false null none nil undefined nan inf self cls this super new return import export default from as
def class function const let var async await yield lambda pass raise try except finally catch throw if else elif
for while break continue switch case public private protected static void int str float bool boolean string number
object any dict list tuple set map array type types interface enum struct value values key keys name names id ids
data item items result results error errors message messages text title description label content body header headers
status code msg info debug warn warning log logs test tests main index init setup config settings options option args
kwargs params param input output request response req res ctx context app api url uri path file files dir src lib
utils util helpers helper common core base model models schema schemas view views get set put post patch delete
create update remove add read write open close run start stop user users admin page size count total limit offset
email password token secret version tag tags env local dev prod production staging development http https json yaml
html css js ts py md txt xml csv utf8 utf-8 latin-1 ascii localhost example foo bar baz todo fixme note
""".split()) | frozenset(w.lower() for w in (
    # language / standard-library vocabulary: shared by every codebase, never a project-specific agreement
    __import__("keyword").kwlist + dir(__import__("builtins")) + dir(str) + dir(dict) + dir(list) + dir(set)
    + dir(bytes) + dir(int) + dir(float) + dir(object) + """
    console document window fetch promise json math date regexp error map set symbol array object number string
    boolean undefined null proxy reflect intl buffer process require module exports then catch finally resolve reject
    length push pop shift unshift slice splice concat includes index_of for_each filter reduce some every find keys
    entries assign freeze parse stringify to_string value_of prototype constructor apply call bind arguments
    property decorator staticmethod classmethod abstractmethod dataclass field fields typing optional union literal
    callable iterable iterator generator sequence mapping prop props state children ref refs key event events target
    python python3 node npm npx pip uv git bash powershell pytest docker
    host port build ignore username user_name first_name last_name full_name created_at updated_at deleted_at is_active
    timestamp timeout retry retries enabled disabled required optional_ nullable unique primary foreign
    """.split()) if not w.startswith("__"))

_CAMEL_1 = re.compile(r"([A-Z]+)([A-Z][a-z])")
_CAMEL_2 = re.compile(r"([a-z0-9])([A-Z])")
_SPLIT = re.compile(r"[_\-\s]+")
_VERSION_WORD = re.compile(r"^v\d+(?:\.\d+)*$")
_TEMPLATES = [
    re.compile(r"\$\{[^}]*\}"),                 # JS template ${x}
    re.compile(r"\{\{[^}]*\}\}"),               # jinja/helm {{ x }}
    re.compile(r"\{[^{}/]*\}"),                 # {id} / f-string {user_id}
    re.compile(r"<[^<>/]*>"),                   # flask <int:id>
    re.compile(r"(?<=/):[A-Za-z_][\w]*"),       # express :id
    re.compile(r"%\(\w+\)[sd]|%[sdif]"),        # printf
]
_PATHLIKE = re.compile(r"^[\w.{}\-~]*(/[\w.{}\-~]*)+/?$")
_IDENT_OR_KEY = re.compile(r"^[A-Za-z_@$][\w.\-:$@]*$")


@dataclass(frozen=True)
class NormToken:
    norm: str        # canonical form used for matching (version kept)
    base: str        # canonical form with version removed
    version: str | None
    is_path: bool


def normalize_template(text: str) -> str:
    """Replace template placeholders with `{}` so `/u/{id}`, `/u/:id`, `/u/${id}` agree."""
    out = text
    for rx in _TEMPLATES:
        out = rx.sub("{}", out)
    return out


def split_words(text: str) -> list[str]:
    s = _CAMEL_1.sub(r"\1_\2", text)
    s = _CAMEL_2.sub(r"\1_\2", s)
    return [w for w in _SPLIT.split(s.lower()) if w]


def normalize(raw: str) -> NormToken | None:
    """Return the canonical token or None when the text is not a plausible agreement token."""
    text = raw.strip().strip("\"'`")
    if not text or len(text) > MAX_TOKEN_LEN or any(c.isspace() for c in text):
        return None
    text = normalize_template(text)
    if text.startswith(("http://", "https://")):
        text = re.sub(r"^https?://", "", text)
    if "/" in text and _PATHLIKE.match(text.lstrip("^")):
        segs = [s for s in text.lower().strip("/").split("/") if s]
        if not segs or all(s == "{}" for s in segs):
            return None
        version = next((s for s in segs if _VERSION_WORD.match(s)), None)
        norm = "/" + "/".join(segs)
        base = "/" + "/".join(s for s in segs if s != version) if version else norm
        return NormToken(norm, base, version, True)
    if not _IDENT_OR_KEY.match(text) and not text.isdigit():
        return None
    if text.isdigit():
        return NormToken(text, text, None, False) if len(text) >= 4 else None
    # dotted keys/topics keep '.' as a structural separator; each part is word-folded
    parts = [ "_".join(split_words(p)) for p in re.split(r"[.:]", text) ]
    parts = [p for p in parts if p]
    if not parts:
        return None
    norm = ".".join(parts)
    words = parts[-1].split("_")
    version = None
    if len(words) > 1 and _VERSION_WORD.match(words[-1]):
        version = words[-1]
        parts = parts[:-1] + ["_".join(words[:-1])]
    else:
        m = re.match(r"^(.*[a-z])(v\d+)$", words[-1])  # e.g. "orderv2" written without separator
        if m and len(words) == 1 and len(m.group(1)) >= 3:
            version = m.group(2)
            parts = parts[:-1] + [m.group(1)]
    base = ".".join(parts)
    return NormToken(norm, base, version, False)


def specificity(tok: NormToken) -> float:
    """Shape-based specificity in [0, 1]. Generic / stoplisted tokens score 0."""
    n = tok.norm
    if tok.is_path:
        segs = [s for s in n.strip("/").split("/") if s not in ("{}",) and not _VERSION_WORD.match(s)]
        if not segs or all(s in STOPWORDS for s in segs):
            return 0.0
        if len(segs) == 1 and len(segs[0]) < 4:
            return 0.0
        return min(1.0, 0.45 + 0.15 * len(segs) + 0.01 * len(n))
    if n.isdigit():
        return 0.3 if len(n) >= 4 else 0.0
    if n in STOPWORDS or tok.base in STOPWORDS:
        return 0.0
    words = [w for w in re.split(r"[._]", n) if w]
    if len(n) < 4:
        return 0.0
    if all(w in STOPWORDS or w.isdigit() for w in words) and len(words) <= 2:
        return 0.15
    if len(words) == 1:
        return min(0.5, 0.1 + 0.035 * len(n))
    return min(1.0, 0.35 + 0.15 * (len(words) - 1) + 0.01 * len(n))


def rarity(df: int, n_files: int) -> float:
    """IDF-style rarity normalized to [0,1]."""
    if n_files <= 0:
        return 0.0
    return max(0.0, math.log((n_files + 1) / (df + 1)) / math.log(n_files + 1)) if n_files > 0 else 0.0


def spread(n_files: int, n_repos: int) -> float:
    if n_files < 2:
        return 0.0
    # 2 files -> 0.40, 3 -> 0.5, 15 -> 1.0; holding across repos multiplies by 1.5
    return min(1.0, math.log2(1 + n_files) / 4 * (1.5 if n_repos > 1 else 1.0))
