from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal


class FileEdit(BaseModel):
    path: str = Field(min_length=1)
    content: str


class CodePlan(BaseModel):
    summary: str
    files: list[FileEdit]
    tests_added_or_updated: bool = False
    notes: str | None = None


DecisionStatus = Literal["approve", "request_changes", "stop"]


class AgentDecision(BaseModel):
    version: int = 1
    issue_number: int
    pr_number: int
    status: DecisionStatus
    iteration: int = 1
    ci_conclusion: Literal["success", "failure"] = "success"
    failed_jobs: list[str] = []
    requirements_satisfied: bool = True
    missing_requirements: list[str] = []
    actions: list[str] = []
    stop_reasons: list[str] = []
