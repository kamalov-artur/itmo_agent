from __future__ import annotations

import json
from typing import Any
import requests


class LLMError(RuntimeError):
    pass


class OpenAICompatibleClient:
    """
    Minimal OpenAI-compatible Chat Completions client.
    Works with many OpenAI-style providers.

    Requires:
      - api_key
      - base_url (default OpenAI)
      - model_name
    """

    def __init__(self, api_key: str, model_name: str, temperature: float, timeout_s: int):
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.timeout_s = timeout_s
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"


    def chat_text(self, messages: list[dict[str, str]]) -> str:
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": self.temperature,
        }
        r = requests.post(
            self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=self.timeout_s,
        )
        if r.status_code >= 300:
            raise LLMError(f"LLM HTTP {r.status_code}: {r.text[:500]}")
        data = r.json()
        try:
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            raise LLMError(f"Unexpected LLM response shape: {data}") from e


class YandexStubClient:
    """
    Placeholder: you can implement YandexGPT API calls here if needed.
    For now it raises to avoid silent misconfiguration.
    """
    def __init__(self, *_: Any, **__: Any):
        pass

    def chat_text(self, messages: list[dict[str, str]]) -> str:
        raise LLMError("YandexGPT client is not implemented in this template.")


def build_llm(provider: str, api_key: str, model_name: str, temperature: float, timeout_s: int):
    if provider.lower() == "openai":
        return OpenAICompatibleClient(api_key, model_name, temperature, timeout_s)
    if provider.lower() == "yandex":
        return YandexStubClient()
    raise LLMError(f"Unknown LLM_PROVIDER: {provider}")
