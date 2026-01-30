from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_DIR = Path("agent_reports")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_report_dir() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)


def write_report(name: str, payload: dict[str, Any]) -> Path:
    ensure_report_dir()
    payload = dict(payload)
    payload.setdefault("timestamp_utc", utc_now_iso())
    path = REPORT_DIR / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def env_summary() -> dict[str, Any]:
    keys = [
        "GITHUB_REPOSITORY",
        "GITHUB_ACTOR",
        "GITHUB_REF",
        "GITHUB_SHA",
        "LLM_PROVIDER",
        "MODEL_NAME",
        "BASE_BRANCH",
        "MAX_ITERS",
    ]
    return {k: os.getenv(k) for k in keys}
