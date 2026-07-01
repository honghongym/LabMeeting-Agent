from __future__ import annotations

import os

from app.llm.base import LLMProvider
from app.llm.mock import MockProvider
from app.llm.tongyi import TongyiProvider


def get_llm_provider(provider_name: str | None = None) -> LLMProvider:
    provider = (provider_name or os.getenv("LLM_PROVIDER", "mock")).lower()
    if provider == "tongyi":
        return TongyiProvider()
    return MockProvider()
