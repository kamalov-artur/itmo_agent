from __future__ import annotations

from dataclasses import dataclass
import os


def _get(name: str, default: str | None = None) -> str:
    val = os.getenv(name)
    if val is None or val == "":
        if default is None:
            raise RuntimeError(f"Missing required env var: {name}")
        return default
    return val


def _get_int(name: str, default: int) -> int:
    val = os.getenv(name)
    if not val:
        return default
    return int(val)


def _get_float(name: str, default: float) -> float:
    val = os.getenv(name)
    if not val:
        return default
    return float(val)


@dataclass(frozen=True)
class Settings:
    github_token: str
    llm_provider: str
    llm_api_key: str
    model_name: str
    base_branch: str
    max_iters: int
    temperature: float
    timeout_seconds: int

    @staticmethod
    def from_env() -> "Settings":
        return Settings(
            github_token=_get("GITHUB_TOKEN"),
            llm_provider=os.getenv("LLM_PROVIDER", "openai"),
            llm_api_key=_get("LLM_API_KEY"),
            model_name=os.getenv("MODEL_NAME", "gpt-4o-mini"),
            base_branch=os.getenv("BASE_BRANCH", "main"),
            max_iters=_get_int("MAX_ITERS", 3),
            temperature=_get_float("LLM_TEMPERATURE", 0.0),
            timeout_seconds=_get_int("LLM_TIMEOUT_SECONDS", 60),
        )


def get_repo_full_name() -> str:
    # GitHub Actions provides this env var; locally user can set it
    repo = os.getenv("GITHUB_REPOSITORY")
    if not repo:
        raise RuntimeError("Missing GITHUB_REPOSITORY env var (e.g. owner/repo).")
    return repo
