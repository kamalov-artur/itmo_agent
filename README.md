# SDLC Agents (Issue -> PR -> CI -> Review -> Fix loops)

## What it does
- When an Issue is opened/edited: a Code Agent (CLI) creates/updates a branch and Pull Request.
- On Pull Request updates: CI runs (ruff/black/mypy/pytest + pip-audit) and a Reviewer Agent posts:
  - PR comment
  - GitHub Actions job summary
  - code review (APPROVE or REQUEST_CHANGES) with a machine-readable AGENT_DECISION block
- When REQUEST_CHANGES is posted: a Fix Cycle workflow runs Code Agent again to apply fixes (up to MAX_ITERS).

## Requirements
- Python 3.11+
- GitHub Actions enabled
- A model API key set in repository secrets:
  - `LLM_API_KEY`
- Optional: set `LLM_PROVIDER` and `MODEL_NAME` (defaults in `.env.example`)

## Setup (GitHub)
1) Add GitHub Secret: `LLM_API_KEY`
2) Optionally add repository variables or secrets:
   - `LLM_PROVIDER` (default: openai)
   - `MODEL_NAME` (default: gpt-4o-mini)
   - `MAX_ITERS` (default: 3)

## Local run (Docker)
```bash
cp .env.example .env
# set LLM_API_KEY in .env
docker compose up -d
docker compose run --rm agent sdlc-agent run-issue --issue-number 1
