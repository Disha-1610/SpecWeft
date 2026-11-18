"""Shell-command and tool-output classification shared by all trajectory adapters."""
from __future__ import annotations

import re
import shlex

TEST_CMD = re.compile(r"(?:^|[\s;&|(])(?:python\d*(?:\.\d+)?\s+-m\s+)?(pytest|py\.test|unittest|nosetests|tox|jest|vitest|mocha|"
                      r"go\s+test|cargo\s+test|mvn\s+(?:-\S+\s+)*test|gradle\w*\s+test|(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?test"
                      r"|rspec|phpunit|ctest|make\s+test)\b")
TEST_SCRIPT = re.compile(r"(?:^|[\s;&|(])python\d*(?:\.\d+)?\s+(?:\S*/)?(?:test_\w+|\w+_test|reproduce\w*|repro\w*)\.py\b")
BUILD_CMD = re.compile(r"(?:^|[\s;&|(])(tsc\b|(?:npm|pnpm|yarn|bun)\s+(?:run\s+)?build|make(?:\s+(?!test)\w+)?\s*$|cargo\s+build|go\s+build|"
                       r"docker\s+build|mvn\s+(?:package|compile|install)|gradle\w*\s+build|pip\s+install\s+-e|python\d*\s+setup\.py\s+(?:build|develop|install)|"
                       r"cmake\s+--build|python\d*\s+-m\s+(?:py_compile|compileall|build))")
READ_CMD = re.compile(r"^\s*(cat|head|tail|less|more|bat|nl|view)\s")
SED_PRINT = re.compile(r"^\s*sed\s+-n\s")
SEARCH_CMD = re.compile(r"^\s*(grep|rg|ag|ack|find|fd|ls|tree|git\s+grep)\b")
EDIT_CMD = re.compile(r"^\s*(sed\s+-i|perl\s+-pi|tee\s|patch\s|git\s+apply)")

FAIL_PATTERNS = re.compile(r"(\bFAILED\b|\bfailed\b|\b\d+ failed\b|Traceback \(most recent call last\)|\bAssertionError\b|"
                           r"\bERROR\b|error TS\d+|SyntaxError|ModuleNotFoundError|ImportError|npm ERR!|Build failed|"
                           r"compilation terminated|\berror\[E\d+\]|exit code [1-9]\d*|Exit code [1-9]\d*)")
PASS_ONLY = re.compile(r"\b\d+ passed\b(?!.*\bfailed\b)", re.S)


def command_kind(cmd: str) -> str | None:
    """test_run | build_run | read | search | edit | None."""
    if TEST_CMD.search(cmd) or TEST_SCRIPT.search(cmd):
        return "test_run"
    if BUILD_CMD.search(cmd):
        return "build_run"
    first = re.split(r"\s*(?:&&|\|\||;|\|)\s*", cmd.strip(), maxsplit=1)[0]
    if EDIT_CMD.match(first):
        return "edit"
    if READ_CMD.match(first) or SED_PRINT.match(first):
        return "read"
    if SEARCH_CMD.match(first):
        return "search"
    return None


def command_paths(cmd: str) -> list[str]:
    """File-like arguments of the first command of a pipeline (best effort)."""
    first = re.split(r"\s*(?:&&|\|\||;|\|)\s*", cmd.strip(), maxsplit=1)[0]
    try:
        args = shlex.split(first, posix=True)
    except ValueError:
        args = first.split()
    out = []
    for a in args[1:]:
        if a.startswith("-") or "*" in a or a in (">", "<"):
            continue
        m = _PATHLIKE_ARG.match(a)
        if m and m.group(1).lower() in FILE_EXTENSIONS:
            out.append(a)
    return out


# an argument is a file only if it is path-shaped AND ends in a known file extension
# (rejects inline code such as `python -c "all(c.repo..."` and module names like `specweft.diffs`)
_PATHLIKE_ARG = re.compile(r"^[\w./\\~:@+\-]+\.([A-Za-z0-9]{1,10})$")
FILE_EXTENSIONS = frozenset("""
py pyi ipynb ts tsx js jsx mjs cjs json yaml yml toml ini cfg conf env md markdown rst txt sql proto graphql gql avsc
tf tfvars hcl go rs java kt kts scala rb php cs c h cc cpp hpp swift m mm sh bash zsh ps1 bat cmd html htm css scss
less vue svelte xml gradle properties lock dockerfile csv tsv log jsonl mod sum
""".split())


def output_failed(output: str, is_error: bool | None = None, exit_code: int | None = None) -> bool:
    if exit_code is not None:
        return exit_code != 0
    if is_error:
        return True
    tail = output[-4000:]
    if PASS_ONLY.search(tail) and not re.search(r"\b\d+ (failed|errors?)\b", tail):
        return False
    return bool(FAIL_PATTERNS.search(tail))


_EXIT = re.compile(r"(?:exit code|Exit code)[: ]+(-?\d+)")


def exit_code_in(output: str) -> int | None:
    m = list(_EXIT.finditer(output[-2000:]))
    return int(m[-1].group(1)) if m else None
