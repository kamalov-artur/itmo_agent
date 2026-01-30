from __future__ import annotations

import json
import os
from typing import Any, List, Dict
import requests


class LLMError(RuntimeError):
    pass


class OpenAICompatibleClient:
    def __init__(self, api_key: str, model_name: str, temperature: float, timeout_s: int):
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.timeout_s = timeout_s
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"

    def chat_text(self, messages: List[Dict[str, str]]) -> str:
        parts: list[str] = []

        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if not content:
                continue

            if role in ("system", "developer"):
                parts.append(f"[INSTRUCTIONS]\n{content}")
            elif role == "assistant":
                parts.append(f"[ASSISTANT_CONTEXT]\n{content}")
            else:
                parts.append(f"[USER]\n{content}")

        collapsed_prompt = "\n\n".join(parts).strip()

        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "user",
                    "content": collapsed_prompt,
                }
            ],
            "temperature": self.temperature,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": f"https://github.com/{os.getenv('GITHUB_REPOSITORY', '')}",
            "X-Title": "itmo_agent_sdlc",
        }

        response = requests.post(
            self.base_url,
            headers=headers,
            data=json.dumps(payload),
            timeout=self.timeout_s,
        )

        if response.status_code >= 300:
            raise LLMError(f"LLM HTTP {response.status_code}: {response.text[:500]}")

        data = response.json()

        try:
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            raise LLMError(f"Unexpected LLM response shape: {data}") from e


def build_llm(
    provider: str,
    api_key: str,
    model_name: str,
    temperature: float,
    timeout_s: int,
):
    provider = provider.lower()

    if provider == "openai":
        return OpenAICompatibleClient(api_key, model_name, temperature, timeout_s)

    raise LLMError(f"Unknown LLM_PROVIDER: {provider}")
