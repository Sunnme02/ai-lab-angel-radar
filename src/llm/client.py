"""Small optional LLM client.

The radar pipeline must work without LLM credentials. This module only runs when
an explicit LLM command is called and a provider key is available.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass

import requests
from dotenv import load_dotenv

from ..config import ROOT


class LLMUnavailable(RuntimeError):
    """Raised when a requested LLM provider is not configured."""


@dataclass
class LLMConfig:
    provider: str = "openai"
    model: str = ""
    temperature: float = 0.2
    timeout: int = 60
    openai_key: str = ""
    anthropic_key: str = ""

    @classmethod
    def from_env(
        cls,
        provider: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
    ) -> "LLMConfig":
        load_dotenv(ROOT / ".env")
        selected = (provider or os.getenv("LLM_PROVIDER") or "openai").strip().lower()
        default_model = "gpt-4o-mini" if selected == "openai" else "claude-3-5-haiku-latest"
        return cls(
            provider=selected,
            model=(model or os.getenv("LLM_MODEL") or default_model).strip(),
            temperature=float(
                temperature
                if temperature is not None
                else os.getenv("LLM_TEMPERATURE", "0.2")
            ),
            timeout=int(os.getenv("LLM_TIMEOUT", "60")),
            openai_key=os.getenv("OPENAI_API_KEY", ""),
            anthropic_key=os.getenv("ANTHROPIC_API_KEY", ""),
        )

    @property
    def available(self) -> bool:
        if self.provider == "openai":
            return bool(self.openai_key)
        if self.provider == "anthropic":
            return bool(self.anthropic_key)
        return False


class LLMClient:
    def __init__(self, config: LLMConfig | None = None):
        self.config = config or LLMConfig.from_env()

    @property
    def available(self) -> bool:
        return self.config.available

    def complete(self, system: str, user: str) -> str:
        if not self.available:
            raise LLMUnavailable(
                f"LLM provider {self.config.provider!r} is not configured. "
                "Set OPENAI_API_KEY or ANTHROPIC_API_KEY, or use --no-llm."
            )
        if self.config.provider == "openai":
            return self._complete_openai(system, user)
        if self.config.provider == "anthropic":
            return self._complete_anthropic(system, user)
        raise LLMUnavailable(f"Unsupported LLM provider: {self.config.provider}")

    def _complete_openai(self, system: str, user: str) -> str:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.config.openai_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.config.model,
                "temperature": self.config.temperature,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=self.config.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return payload["choices"][0]["message"]["content"].strip()

    def _complete_anthropic(self, system: str, user: str) -> str:
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.config.anthropic_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json={
                "model": self.config.model,
                "temperature": self.config.temperature,
                "max_tokens": 1800,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            timeout=self.config.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return "".join(
            block.get("text", "")
            for block in payload.get("content", [])
            if block.get("type") == "text"
        ).strip()


def extract_json(text: str) -> dict:
    """Extract the first JSON object from an LLM response."""
    text = (text or "").strip()
    if not text:
        raise ValueError("Empty LLM response")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if match:
        return json.loads(match.group(1))
    match = re.search(r"(\{.*\})", text, re.S)
    if match:
        return json.loads(match.group(1))
    raise ValueError("Cannot find a JSON object in LLM response")

