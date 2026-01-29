from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..config import Settings
from ..github.client import GithubClient
from ..llm.client import build_llm, LLMError
from ..logging import write_report, env_summary
from ..state.protocol import CodePlan


DECISION_RE = re.compile(r"<!--\s*AGENT_DECISION.*?-->", re.DOTALL)


LABEL_IN_PROGRESS = "agent:in-progress"
LABEL_DONE = "agent:done"
LABEL_FAILED = "agent:failed"


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def _git(*args: str) -> None:
    _run(["git", *args])


def _load_prompt(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _write_files(plan: CodePlan) -> list[str]:
    changed: list[str] = []
    for f in plan.files:
        p = Path(f.path)
        p.parent.mkdir(parents=True, exist_ok=True)
        old = p.read_text(encoding="utf-8") if p.exists() else None
        p.write_text(f.content, encoding="utf-8")
        if old != f.content:
            changed.append(f.path)
    return changed


def _quality_checks() -> dict[str, Any]:
    result: dict[str, Any] = {"ruff": None, "black": None, "mypy": None, "pytest": None}
    cmds = [
        ("ruff", ["ruff", "check", "."]),
        ("black", ["black", "--check", "."]),
        ("mypy", ["mypy", "src"]),
        ("pytest", ["pytest", "-q"]),
    ]
    for name, cmd in cmds:
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            result[name] = "ok"
        except subprocess.CalledProcessError as e:
            result[name] = {"status": "fail", "stdout": e.stdout[-2000:], "stderr": e.stderr[-2000:]}
            break
    return result


def _extract_issue_number_from_text(text: str) -> int | None:
    m = re.search(r"(?im)^\s*fixes\s+#(\d+)\s*$", text or "")
    if not m:
        return None
    return int(m.group(1))


def _parse_decision_block(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    m = DECISION_RE.search(text)
    if not m:
        return None
    block = m.group(0)
    # naive parse for a few keys
    def g(key: str) -> str | None:
        mm = re.search(rf"(?m)^\s*{re.escape(key)}:\s*(.+)\s*$", block)
        return mm.group(1).strip() if mm else None

    iteration_s = g("iteration")
    status = g("status")
    issue_s = g("issue_number")
    return {
        "status": status,
        "iteration": int(iteration_s) if iteration_s and iteration_s.isdigit() else None,
        "issue_number": int(issue_s) if issue_s and issue_s.isdigit() else None,
        "raw": block,
    }


def run_issue(*, settings: Settings, gh: GithubClient, issue_number: int) -> None:
    issue = gh.get_issue(issue_number)

    # Safety: if already done, exit
    if LABEL_DONE in issue.labels:
        write_report(f"code_issue_{issue_number}_skipped", {"reason": "already_done", "env": env_summary()})
        return

    # Mark in progress
    try:
        gh.add_issue_labels(issue_number, [LABEL_IN_PROGRESS])
    except Exception:
        pass

    base_branch = settings.base_branch
    branch = f"agent/issue-{issue_number}"

    # Prepare git
    _git("config", "user.email", "github-actions[bot]@users.noreply.github.com")
    _git("config", "user.name", "github-actions[bot]")
    _git("checkout", base_branch)
    _git("pull", "--ff-only", "origin", base_branch)
    # create or reset branch
    _git("checkout", "-B", branch)

    # LLM plan
    file_tree = _list_repo_files(limit=400)
    prompt = _load_prompt("src/sdlc_agents/llm/prompts/code_agent.md")

    try:
        llm = build_llm(
            settings.llm_provider,
            settings.llm_api_key,
            settings.model_name,
            settings.temperature,
            settings.timeout_seconds,
        )

        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": (
                    f"Issue #{issue_number}\nTitle: {issue.title}\nBody:\n{issue.body}\n\n"
                    "Partial repo file tree:\n"
                    + "\n".join(file_tree)
                    + "\n\n"
                    "Return JSON plan with full file contents."
                ),
            },
        ]
        raw = llm.chat_text(messages)
        plan = CodePlan.model_validate_json(raw)
    except (LLMError, ValidationError) as e:
        gh.comment_issue(issue_number, f"Agent failed to generate a valid plan: {str(e)[:500]}")
        gh.add_issue_labels(issue_number, [LABEL_FAILED])
        gh.remove_issue_labels(issue_number, [LABEL_IN_PROGRESS])
        write_report(
            f"code_issue_{issue_number}_failed",
            {"env": env_summary(), "issue": issue_number, "error": str(e)},
        )
        return

    changed = _write_files(plan)

    if not changed:
        gh.comment_issue(issue_number, "Agent produced no changes. Stopping.")
        gh.add_issue_labels(issue_number, [LABEL_FAILED])
        gh.remove_issue_labels(issue_number, [LABEL_IN_PROGRESS])
        return

    # Run quick checks locally
    qc = _quality_checks()

    # Commit & push
    _git("add", "-A")
    _git("commit", "-m", f"Agent: implement issue #{issue_number} (iter 1)")
    _git("push", "-u", "origin", branch, "--force")

    pr_title = f"Issue #{issue_number}: {issue.title[:80]}"
    pr_body = f"Fixes #{issue_number}\n\nAgent summary:\n- {plan.summary}\n"
    pr = gh.create_or_get_pr(head_ref=branch, base_ref=base_branch, title=pr_title, body=pr_body)

    try:
        gh.add_pr_labels(pr.number, ["agent:active"])
    except Exception:
        pass

    gh.comment_issue(issue_number, f"Created/updated PR #{pr.number} for Issue #{issue_number}.")

    write_report(
        f"code_issue_{issue_number}",
        {
            "env": env_summary(),
            "issue_number": issue_number,
            "branch": branch,
            "pr_number": pr.number,
            "changed_files": changed,
            "quality_checks": qc,
            "plan_summary": plan.summary,
        },
    )


def run_pr_iteration(*, settings: Settings, gh: GithubClient, pr_number: int) -> None:
    pr = gh.get_pr(pr_number)
    issue_number = gh.extract_issue_number_from_pr_body(pr.body or "")
    if issue_number is None:
        gh.comment_pr(pr_number, "Cannot iterate: PR is not linked to an Issue (missing `Fixes #N`).")
        return

    issue = gh.get_issue(issue_number)

    last_bot_review = gh.get_latest_bot_review_body(pr_number)
    decision = _parse_decision_block(last_bot_review or "")

    if not decision:
        gh.comment_pr(pr_number, "Cannot iterate: no AGENT_DECISION found in latest bot review.")
        return

    status = decision.get("status")
    iteration = decision.get("iteration") or 1

    if status == "approve":
        # finalize labels
        try:
            gh.remove_issue_labels(issue_number, [LABEL_IN_PROGRESS])
            gh.add_issue_labels(issue_number, [LABEL_DONE])
        except Exception:
            pass
        gh.comment_issue(issue_number, f"Reviewer approved PR #{pr_number}. Marking as done.")
        write_report(
            f"code_pr_{pr_number}_finalized",
            {"env": env_summary(), "pr_number": pr_number, "issue_number": issue_number},
        )
        return

    if iteration >= settings.max_iters:
        gh.comment_pr(pr_number, f"Stopping: reached MAX_ITERS={settings.max_iters}.")
        try:
            gh.remove_issue_labels(issue_number, [LABEL_IN_PROGRESS])
            gh.add_issue_labels(issue_number, [LABEL_FAILED])
        except Exception:
            pass
        write_report(
            f"code_pr_{pr_number}_stopped",
            {"env": env_summary(), "pr_number": pr_number, "issue_number": issue_number, "iteration": iteration},
        )
        return

    # Prepare git branch (same branch as PR head)
    branch = pr.head_ref
    base_branch = settings.base_branch

    _git("config", "user.email", "github-actions[bot]@users.noreply.github.com")
    _git("config", "user.name", "github-actions[bot]")
    _git("checkout", base_branch)
    _git("pull", "--ff-only", "origin", base_branch)
    _git("checkout", branch)
    _git("pull", "--ff-only", "origin", branch)

    # LLM fix plan
    file_tree = _list_repo_files(limit=400)
    prompt = _load_prompt("src/sdlc_agents/llm/prompts/code_agent.md")
    diff = gh.get_pr_diff(pr_number)

    try:
        llm = build_llm(
            settings.llm_provider,
            settings.llm_api_key,
            settings.model_name,
            settings.temperature,
            settings.timeout_seconds,
        )
        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": (
                    f"Iterate on PR #{pr_number} for Issue #{issue_number}\n"
                    f"Issue title: {issue.title}\nIssue body:\n{issue.body}\n\n"
                    f"Reviewer decision block:\n{decision.get('raw','')}\n\n"
                    "PR diff (truncated):\n"
                    f"{diff}\n\n"
                    "Partial repo file tree:\n"
                    + "\n".join(file_tree)
                    + "\n\n"
                    "Return JSON plan with full file contents to fix issues."
                ),
            },
        ]
        raw = llm.chat_text(messages)
        plan = CodePlan.model_validate_json(raw)
    except (LLMError, ValidationError) as e:
        gh.comment_pr(pr_number, f"Agent failed to generate a valid fix plan: {str(e)[:500]}")
        try:
            gh.remove_issue_labels(issue_number, [LABEL_IN_PROGRESS])
            gh.add_issue_labels(issue_number, [LABEL_FAILED])
        except Exception:
            pass
        write_report(
            f"code_pr_{pr_number}_failed",
            {"env": env_summary(), "pr_number": pr_number, "issue_number": issue_number, "error": str(e)},
        )
        return

    changed = _write_files(plan)
    if not changed:
        gh.comment_pr(pr_number, "Agent produced no changes during iteration. Stopping.")
        try:
            gh.remove_issue_labels(issue_number, [LABEL_IN_PROGRESS])
            gh.add_issue_labels(issue_number, [LABEL_FAILED])
        except Exception:
            pass
        return

    qc = _quality_checks()

    _git("add", "-A")
    _git("commit", "-m", f"Agent: fix for issue #{issue_number} (iter {iteration + 1})")
    _git("push", "origin", branch)

    gh.comment_pr(pr_number, f"Pushed iteration {iteration + 1}. Updated files: {', '.join(changed[:10])}")

    write_report(
        f"code_pr_{pr_number}_iter_{iteration+1}",
        {
            "env": env_summary(),
            "issue_number": issue_number,
            "pr_number": pr_number,
            "iteration": iteration + 1,
            "changed_files": changed,
            "quality_checks": qc,
            "plan_summary": plan.summary,
        },
    )


def _list_repo_files(limit: int = 400) -> list[str]:
    out: list[str] = []
    for p in Path(".").rglob("*"):
        if p.is_dir():
            continue
        if ".git" in p.parts:
            continue
        # skip large/common noise
        if p.name.endswith((".png", ".jpg", ".jpeg", ".gif", ".pdf")):
            continue
        rel = str(p)
        out.append(rel)
        if len(out) >= limit:
            break
    return out
