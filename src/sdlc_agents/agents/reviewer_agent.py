from __future__ import annotations

import re
from pathlib import Path

from ..config import Settings
from ..github.client import GithubClient
from ..github.publish import make_agent_decision_block
from ..llm.client import build_llm, LLMError
from ..logging import write_report, env_summary


DECISION_RE = re.compile(r"<!--\s*AGENT_DECISION.*?-->", re.DOTALL)


def _load_prompt(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def run_reviewer(*, settings: Settings, gh: GithubClient, pr_number: int, ci_conclusion: str) -> None:
    pr = gh.get_pr(pr_number)
    issue_number = gh.extract_issue_number_from_pr_body(pr.body or "")
    if issue_number is None:
        # Without a linked issue, we still review but we can't do requirement check
        issue_title = ""
        issue_body = ""
        issue_number = 0
    else:
        issue = gh.get_issue(issue_number)
        issue_title = issue.title
        issue_body = issue.body

    files = gh.get_pr_files(pr_number)
    diff = gh.get_pr_diff(pr_number)

    ci_ok = (ci_conclusion or "").lower() == "success"

    # Minimal requirement satisfaction logic:
    # - If no linked issue => unknown => request_changes (to enforce linkage)
    requirements_satisfied = True
    missing: list[str] = []
    if issue_number == 0:
        requirements_satisfied = False
        missing.append("PR body must include `Fixes #<issue_number>` to link requirements.")
    if not ci_ok:
        requirements_satisfied = False

    status = "approve" if (ci_ok and requirements_satisfied) else "request_changes"
    failed_jobs = [] if ci_ok else ["quality"]

    # Try to produce a better human review with LLM; if LLM fails, fallback.
    review_text = ""
    try:
        llm = build_llm(
            settings.llm_provider,
            settings.llm_api_key,
            settings.model_name,
            settings.temperature,
            settings.timeout_seconds,
        )
        prompt = _load_prompt("src/sdlc_agents/llm/prompts/reviewer.md")
        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": (
                    f"Issue:\nTitle: {issue_title}\nBody:\n{issue_body}\n\n"
                    f"PR #{pr_number}\nFiles:\n- " + "\n- ".join(files) + "\n\n"
                    f"CI conclusion: {ci_conclusion}\n\n"
                    f"Diff (truncated):\n{diff}\n"
                    f"\nDecision precomputed:\nstatus={status}\n"
                    "Write a review comment with key points and action items."
                ),
            },
        ]
        review_text = llm.chat_text(messages).strip()
    except LLMError as e:
        review_text = (
            "Automated review (fallback):\n"
            f"- CI conclusion: **{ci_conclusion}**\n"
            f"- Linked issue: **{issue_number if issue_number else 'missing'}**\n"
            f"- Changed files: {len(files)}\n"
            f"- Notes: {str(e)[:200]}"
        )

    # Determine iteration from previous decisions if possible (parse from last bot review)
    last_review = gh.get_latest_bot_review_body(pr_number)
    iteration = 1
    if last_review and DECISION_RE.search(last_review):
        # very simple parse
        m = re.search(r"iteration:\s*(\d+)", last_review)
        if m:
            iteration = int(m.group(1)) + 1

    decision_block = make_agent_decision_block(
        issue_number=issue_number,
        pr_number=pr_number,
        status=status,
        iteration=iteration,
        ci_conclusion="success" if ci_ok else "failure",
        failed_jobs=failed_jobs,
        requirements_satisfied=requirements_satisfied,
        missing_requirements=missing,
        actions=(["Fix CI failures and ensure requirements are satisfied."] if status != "approve" else ["none"]),
        stop_reasons=[],
    )

    # Publish: PR comment + Review
    full_comment = f"{review_text}\n\n{decision_block}"
    gh.comment_pr(pr_number, full_comment)

    event = "APPROVE" if status == "approve" else "REQUEST_CHANGES"
    gh.submit_review(pr_number, body=full_comment, event=event)

    if status == "approve":
        try:
            gh.add_pr_labels(pr_number, ["agent:approved"])
        except Exception:
            pass

    write_report(
        f"reviewer_pr_{pr_number}",
        {
            "env": env_summary(),
            "pr_number": pr_number,
            "linked_issue": issue_number,
            "ci_conclusion": ci_conclusion,
            "status": status,
            "iteration": iteration,
            "files_count": len(files),
        },
    )
