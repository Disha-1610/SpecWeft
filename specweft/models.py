"""Shared data structures. `Recommendation` is THE evidence schema consumed by API, UI, CLI and hook."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

EventKind = Literal["search", "read", "edit", "test_run", "test_fail", "build_run", "build_fail", "commit", "review"]
# `commit` / `review` only occur in Bitbucket PR sessions (traces/bitbucket_pr.py)
EVENT_KINDS: tuple[str, ...] = ("search", "read", "edit", "test_run", "test_fail", "build_run", "build_fail",
                                "commit", "review")


@dataclass(frozen=True)
class RawToken:
    """A token produced by an extractor (before normalization)."""
    text: str
    kind: str          # e.g. string, identifier, config_key, config_value, sql_table, route, env_var ...
    line: int          # 1-based
    col: int = 0       # 0-based
    context: str = ""  # short source excerpt


@dataclass
class NormalizedEvent:
    """One step of a trajectory, source-independent."""
    seq: int
    kind: str
    path: str | None = None       # repo-relative path after mapping (None for e.g. test_run without file)
    raw_path: str | None = None   # path as written in the trajectory
    excerpt: str = ""
    ts: str | None = None

    def __post_init__(self) -> None:
        if self.kind not in EVENT_KINDS:
            raise ValueError(f"unknown event kind {self.kind!r}")


@dataclass
class NormalizedSession:
    source: str                   # claude_code | swe_agent | openhands | bitbucket_pr
    external_id: str
    repo_name: str | None
    events: list[NormalizedEvent]
    commit_sha: str | None = None
    started_at: str | None = None
    cwd: str | None = None
    gold_files: list[str] | None = None   # files of the resolved patch, if known


@dataclass
class Location:
    repo: str
    path: str
    line: int | None = None
    text: str | None = None


@dataclass
class AgreementEvidence:
    token: str                    # normalized token
    change_type: str              # removed | renamed | value_changed | touched
    token_score: float
    changed_site: Location        # where the change happened
    holder_site: Location         # where the agreement is still held
    renamed_to: str | None = None
    old_value: str | None = None
    new_value: str | None = None


@dataclass
class NavigationEvidence:
    sessions_with_edge: int       # sessions where agent went changed -> related after editing changed
    sessions_editing_source: int
    baseline_rate: float
    lift: float
    detours: int                  # of those, how many happened after a test/build failure
    excerpts: list[str] = field(default_factory=list)


@dataclass
class Recommendation:
    changed_file: Location
    related_file: Location
    reason: str
    agreement_evidence: list[AgreementEvidence]
    navigation_evidence: NavigationEvidence | None
    cross_repo: bool
    features: dict[str, float]
    ranking_score: float
    confidence: str               # high | medium | low
    confidence_score: float
    confidence_basis: str         # "logistic_regression" | "uncalibrated_weighted"
    explanation: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
