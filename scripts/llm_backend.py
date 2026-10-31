"""
Abstract LLM layer — only OpenAI backend.
Requires OPENAI_API_KEY in .env.
"""
import os
from abc import ABC, abstractmethod


class LLMBackend(ABC):
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def ask(self, prompt: str) -> str: ...


class OpenAIBackend(LLMBackend):
    """OpenAI API (gpt-4o-mini by default)."""
    def __init__(self):
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY missing from .env")
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError("Install with: pip install openai")
        self.client = OpenAI(api_key=api_key, timeout=60.0, max_retries=1)
        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    def name(self) -> str:
        return f"openai:{self.model}"

    def ask(self, prompt: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
        )
        self.last_response = {"model": resp.model, "response_id": resp.id,
                              "system_fingerprint": getattr(resp, "system_fingerprint", None),
                              "usage": resp.usage.model_dump() if resp.usage else None}
        return (resp.choices[0].message.content or "").strip()


def get_backend() -> LLMBackend:
    """Return the configured backend (only OpenAI supported)."""
    name = os.environ.get("LLM_BACKEND", "openai").lower()
    if name != "openai":
        raise RuntimeError(f"LLM_BACKEND='{name}' is not supported, use 'openai'")
    return OpenAIBackend()
