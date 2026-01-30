from __future__ import annotations

import re
from github import Github
from github.Repository import Repository
from github.PullRequest import PullRequest
from github.Issue import Issue
from github.PullRequestReview import PullRequestReview

from .models import IssueData, PRData


FIXES_RE = re.compile(r"(?im)^\s*fixes\s+#(\d+)\s*$")


class GithubClient:
    def __init__(self, token: str, repo_full_name: str):
        self.gh = Github(token)
        self.repo: Repository = self.gh.get_repo(repo_full_name)

    def get_issue(self, number: int) -> IssueData:
        issue: Issue = self.repo.get_issue(number=number)
        labels = {l.name for l in issue.get_labels()}
        return IssueData(number=issue.number, title=issue.title or "", body=issue.body or "", labels=labels)

    def add_issue_labels(self, number: int, labels: list[str]) -> None:
        issue: Issue = self.repo.get_issue(number=number)
        issue.add_to_labels(*labels)

    def remove_issue_labels(self, number: int, labels: list[str]) -> None:
        issue: Issue = self.repo.get_issue(number=number)
        existing = {l.name for l in issue.get_labels()}
        to_remove = [x for x in labels if x in existing]
        if to_remove:
            issue.remove_from_labels(*to_remove)

    def comment_issue(self, number: int, body: str) -> None:
        issue: Issue = self.repo.get_issue(number=number)
        issue.create_comment(body)

    def find_open_pr_by_head(self, head_ref: str) -> PullRequest | None:
        for pr in self.repo.get_pulls(state="open"):
            if pr.head.ref == head_ref:
                return pr
        return None

    def create_or_get_pr(self, head_ref: str, base_ref: str, title: str, body: str) -> PRData:
        pr = self.find_open_pr_by_head(head_ref)
        if pr is None:
            pr = self.repo.create_pull(title=title, body=body, head=head_ref, base=base_ref, draft=False)
        else:
            pr.edit(title=title, body=body)
        return PRData(
            number=pr.number,
            title=pr.title or "",
            body=pr.body or "",
            head_ref=pr.head.ref,
            base_ref=pr.base.ref,
        )

    def get_pr(self, number: int) -> PRData:
        pr: PullRequest = self.repo.get_pull(number=number)
        return PRData(
            number=pr.number,
            title=pr.title or "",
            body=pr.body or "",
            head_ref=pr.head.ref,
            base_ref=pr.base.ref,
        )

    def add_pr_labels(self, pr_number: int, labels: list[str]) -> None:
        pr: PullRequest = self.repo.get_pull(number=pr_number)
        pr.add_to_labels(*labels)

    def comment_pr(self, pr_number: int, body: str) -> None:
        pr: PullRequest = self.repo.get_pull(number=pr_number)
        pr.create_issue_comment(body)

    def submit_review(self, pr_number: int, body: str, event: str) -> PullRequestReview:
        pr: PullRequest = self.repo.get_pull(number=pr_number)
        return pr.create_review(body=body, event=event)

    def get_pr_files(self, pr_number: int, max_files: int = 50) -> list[str]:
        pr: PullRequest = self.repo.get_pull(number=pr_number)
        out: list[str] = []
        for f in pr.get_files():
            out.append(f.filename)
            if len(out) >= max_files:
                break
        return out

    def get_pr_diff(self, pr_number: int, max_chars: int = 300_000) -> str:
        pr: PullRequest = self.repo.get_pull(number=pr_number)
        parts: list[str] = []
        for f in pr.get_files():
            if f.patch:
                parts.append(f"diff -- {f.filename}\n{f.patch}\n")
            if sum(len(p) for p in parts) > max_chars:
                break
        diff = "\n".join(parts)
        return diff[:max_chars]

    def extract_issue_number_from_pr_body(self, pr_body: str) -> int | None:
        m = FIXES_RE.search(pr_body or "")
        if not m:
            return None
        return int(m.group(1))

    def get_latest_bot_review_body(self, pr_number: int, bot_login: str = "github-actions[bot]") -> str | None:
        pr: PullRequest = self.repo.get_pull(number=pr_number)
        reviews = list(pr.get_reviews())
        for rv in reversed(reviews):
            if rv.user and rv.user.login == bot_login and (rv.body or ""):
                return rv.body
        return None
