from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class IssueData:
    number: int
    title: str
    body: str
    labels: set[str]


@dataclass(frozen=True)
class PRData:
    number: int
    title: str
    body: str
    head_ref: str
    base_ref: str
