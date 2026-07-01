from __future__ import annotations

import os

from app.llm.base import LLMProvider
from app.llm.mock import MockProvider
from app.llm.tongyi import TongyiProvider


def get_llm_provider() -> LLMProvider:
    provider = os.getenv("LLM_PROVIDER", "mock").lower()
    if provider == "tongyi":
        return TongyiProvider()
    return MockProvider()

