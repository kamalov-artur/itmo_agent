from __future__ import annotations

import typer

from .config import Settings, get_repo_full_name
from .github.client import GithubClient
from .agents.code_agent import run_issue, run_pr_iteration
from .agents.reviewer_agent import run_reviewer

app = typer.Typer(no_args_is_help=True)


@app.command()
def run_issue(issue_number: int = typer.Option(..., help="GitHub Issue number")) -> None:
    settings = Settings.from_env()
    repo = get_repo_full_name()
    gh = GithubClient(settings.github_token, repo)
    run_issue(settings=settings, gh=gh, issue_number=issue_number)


@app.command()
def run_pr(pr_number: int = typer.Option(..., help="GitHub PR number")) -> None:
    settings = Settings.from_env()
    repo = get_repo_full_name()
    gh = GithubClient(settings.github_token, repo)
    run_pr_iteration(settings=settings, gh=gh, pr_number=pr_number)


@app.command()
def reviewer(
    pr_number: int = typer.Option(..., help="GitHub PR number"),
    ci_conclusion: str = typer.Option("success", help="CI conclusion: success/failure"),
) -> None:
    settings = Settings.from_env()
    repo = get_repo_full_name()
    gh = GithubClient(settings.github_token, repo)
    run_reviewer(settings=settings, gh=gh, pr_number=pr_number, ci_conclusion=ci_conclusion)
