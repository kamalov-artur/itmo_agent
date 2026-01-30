from __future__ import annotations

def make_agent_decision_block(
    *,
    issue_number: int,
    pr_number: int,
    status: str,
    iteration: int,
    ci_conclusion: str,
    failed_jobs: list[str],
    requirements_satisfied: bool,
    missing_requirements: list[str],
    actions: list[str],
    stop_reasons: list[str],
) -> str:
    lines: list[str] = []
    lines.append("<!-- AGENT_DECISION")
    lines.append("version: 1")
    lines.append(f"issue_number: {issue_number}")
    lines.append(f"pr_number: {pr_number}")
    lines.append(f"status: {status}")
    lines.append(f"iteration: {iteration}")
    lines.append("ci:")
    lines.append(f"  conclusion: {ci_conclusion}")
    lines.append("  failed_jobs:")
    if failed_jobs:
        for j in failed_jobs:
            lines.append(f'    - "{j}"')
    else:
        lines.append("    -")
    lines.append("requirements:")
    lines.append(f"  satisfied: {'true' if requirements_satisfied else 'false'}")
    lines.append("  missing:")
    if missing_requirements:
        for x in missing_requirements:
            lines.append(f'    - "{x}"')
    else:
        lines.append("    -")
    lines.append("actions:")
    if actions:
        for a in actions:
            lines.append(f'  - "{a}"')
    else:
        lines.append('  - "none"')
    lines.append("stop_reasons:")
    if stop_reasons:
        for s in stop_reasons:
            lines.append(f'  - "{s}"')
    else:
        lines.append("  -")
    lines.append("-->")
    return "\n".join(lines)
