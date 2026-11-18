"""Infrastructure extraction: Terraform, Kubernetes manifests, Docker (Dockerfile + compose), CI configuration."""
from __future__ import annotations

import re

from ..models import RawToken
from .config import Entry, entries_to_tokens, tolerant_yaml_entries, yaml_entries

# ---------- Kubernetes ----------

def is_k8s(text: str) -> bool:
    return bool(re.search(r"^\s*apiVersion\s*:", text, re.M) and re.search(r"^\s*kind\s*:", text, re.M))


def _k8s_tagger(e: Entry) -> tuple[str, str] | None:
    kp, key = e.keypath, e.key
    if key == "name" and len(kp) >= 2 and kp[-2] == "metadata":
        return ("", "k8s_name")
    if key == "name" and len(kp) >= 3 and kp[-3] == "env":
        return ("", "env_var")
    if key == "name" and "containers" in kp and len(kp) >= 2 and kp[-2] == "[]":
        return ("", "container_name")
    if key in ("containerPort", "port", "targetPort", "nodePort"):
        return ("", "port")
    if key == "image":
        return ("", "image")
    if len(kp) >= 2 and kp[-2] in ("labels", "matchLabels", "selector"):
        return ("label_key", "label_value")
    if key in ("serviceName", "secretName", "configMapName") or (key == "name" and len(kp) >= 2 and kp[-2] in ("secretKeyRef", "configMapKeyRef", "configMapRef", "secretRef")):
        return ("", "k8s_ref")
    if key == "key" and len(kp) >= 2 and kp[-2] in ("secretKeyRef", "configMapKeyRef"):
        return ("", "config_key")
    if key in ("kind", "apiVersion"):
        return ("", "")
    if len(kp) >= 2 and kp[-2] == "data" and kp[0] == "data":
        return ("config_key", "config_value")
    return None


def extract_k8s(text: str) -> list[RawToken]:
    return entries_to_tokens(tolerant_yaml_entries(text), text.splitlines(), _k8s_tagger, default_key_kind="", default_value_kind="config_value")

# ---------- docker-compose ----------

def _compose_tagger(e: Entry) -> tuple[str, str] | None:
    kp = e.keypath
    if len(kp) == 2 and kp[0] == "services":
        return ("service", "")
    if len(kp) >= 3 and kp[0] == "services" and kp[2] == "environment":
        return ("env_var", "config_value")
    if e.key == "image":
        return ("", "image")
    if len(kp) >= 3 and kp[0] == "services" and kp[2] in ("depends_on", "networks", "volumes", "ports"):
        return ("service", "config_value")
    return None


def extract_compose(text: str) -> list[RawToken]:
    toks = entries_to_tokens(yaml_entries(text), text.splitlines(), _compose_tagger, default_key_kind="")
    out: list[RawToken] = []
    for t in toks:  # list-form environment "KEY=value"
        if t.kind == "config_value" and "=" in t.text and re.match(r"^[A-Z_][A-Z0-9_]*=", t.text):
            k, v = t.text.split("=", 1)
            out.append(RawToken(k, "env_var", t.line, t.col, t.context))
            if v:
                out.append(RawToken(v, "config_value", t.line, t.col, t.context))
        else:
            out.append(t)
    return out

# ---------- CI (GitHub Actions / GitLab CI) ----------

def _ci_tagger(e: Entry) -> tuple[str, str] | None:
    kp = e.keypath
    if len(kp) == 2 and kp[0] == "jobs":
        return ("ci_job", "")
    if "env" in kp[:-1] and e.key is not None and kp[-2] == "env":
        return ("env_var", "config_value")
    if e.key == "needs" or (len(kp) >= 2 and kp[-2] == "needs"):
        return ("", "ci_job")
    if e.key in ("uses", "runs-on", "shell", "if", "name"):
        return ("", "")
    if e.key == "run":
        return ("", "")  # shell scripts: references extracted from ${{ }} below
    return None


def extract_ci(text: str) -> list[RawToken]:
    lines = text.splitlines()
    toks = entries_to_tokens(yaml_entries(text), lines, _ci_tagger, default_key_kind="")
    for i, line in enumerate(lines, start=1):
        for m in re.finditer(r"\$\{\{\s*(?:secrets|env|vars)\.([\w-]+)\s*\}\}", line):
            toks.append(RawToken(m.group(1), "env_var", i, m.start(1), line.strip()[:200]))
    return toks

# ---------- Dockerfile ----------

_DOCKER = re.compile(r"^\s*(FROM|ENV|ARG|EXPOSE|COPY|ADD|WORKDIR|ENTRYPOINT|CMD|LABEL)\s+(.*)$", re.I)


def extract_dockerfile(text: str) -> list[RawToken]:
    out: list[RawToken] = []
    for i, line in enumerate(text.splitlines(), start=1):
        m = _DOCKER.match(line)
        if not m:
            continue
        instr, rest = m.group(1).upper(), m.group(2).strip()
        ctx = line.strip()[:200]
        if instr == "FROM":
            parts = rest.split()
            out.append(RawToken(parts[0], "image", i, 0, ctx))
            if len(parts) >= 3 and parts[1].lower() == "as":
                out.append(RawToken(parts[2], "docker_stage", i, 0, ctx))
        elif instr in ("ENV", "ARG", "LABEL"):
            for km in re.finditer(r"([A-Za-z_][\w.]*)\s*[= ]\s*(\"[^\"]*\"|\S+)?", rest):
                out.append(RawToken(km.group(1), "env_var" if instr != "LABEL" else "label_key", i, 0, ctx))
                if km.group(2):
                    out.append(RawToken(km.group(2).strip('"'), "config_value", i, 0, ctx))
        elif instr == "EXPOSE":
            for p in rest.split():
                out.append(RawToken(p.split("/")[0], "port", i, 0, ctx))
        else:
            for piece in re.findall(r"[\w./${}\-]+", rest):
                if "/" in piece or "$" in piece:
                    out.append(RawToken(piece, "path", i, 0, ctx))
        for vm in re.finditer(r"\$\{?([A-Z_][A-Z0-9_]*)\}?", rest):
            out.append(RawToken(vm.group(1), "env_var", i, 0, ctx))
    return out

# ---------- Terraform ----------

_TF_BLOCK = re.compile(r'^\s*(resource|data)\s+"([\w-]+)"\s+"([\w-]+)"')
_TF_NAMED = re.compile(r'^\s*(variable|output|module|provider)\s+"([\w-]+)"')
_TF_REF = re.compile(r"\b(var|local|module|data)\.([\w-]+)")
_TF_STR = re.compile(r'"([^"\n]*)"')
_TF_ATTR = re.compile(r"^\s*([\w-]+)\s*=")


def extract_terraform(text: str) -> list[RawToken]:
    out: list[RawToken] = []
    for i, line in enumerate(text.splitlines(), start=1):
        code = re.split(r"\s(?:#|//)", " " + line, 1)[0][1:]
        ctx = line.strip()[:200]
        if m := _TF_BLOCK.match(code):
            out.append(RawToken(m.group(2), "tf_resource_type", i, m.start(2), ctx))
            out.append(RawToken(m.group(3), "tf_resource_name", i, m.start(3), ctx))
            continue
        if m := _TF_NAMED.match(code):
            out.append(RawToken(m.group(2), f"tf_{m.group(1)}", i, m.start(2), ctx))
            continue
        if m := _TF_ATTR.match(code):
            out.append(RawToken(m.group(1), "tf_attribute", i, m.start(1), ctx))
        for m in _TF_REF.finditer(code):
            kind = {"var": "tf_variable", "local": "tf_local", "module": "tf_module", "data": "tf_resource_type"}[m.group(1)]
            out.append(RawToken(m.group(2), kind, i, m.start(2), ctx))
        for m in _TF_STR.finditer(code):
            out.append(RawToken(m.group(1), "config_value", i, m.start(1), ctx))
    return out
