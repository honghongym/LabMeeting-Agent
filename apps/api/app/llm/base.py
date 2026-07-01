from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from app.agent.chunking import TranscriptChunk
from app.core.enums import MeetingType


@dataclass(frozen=True)
class LLMUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0


@dataclass(frozen=True)
class MapExtraction:
    chunk_id: str
    payload: dict[str, Any]
    rolling_state: dict[str, Any]
    usage: LLMUsage


class LLMProvider(ABC):
    @abstractmethod
    async def extract_chunk(
        self,
        *,
        meeting_type: MeetingType,
        chunk: TranscriptChunk,
        schema_hint: dict[str, Any],
        rolling_state: dict[str, Any],
        historical_memory: list[dict[str, Any]],
    ) -> MapExtraction:
        raise NotImplementedError

    @abstractmethod
    async def reduce(
        self,
        *,
        meeting_type: MeetingType,
        map_results: list[MapExtraction],
        historical_memory: list[dict[str, Any]],
        speaker_mapping: dict[str, str],
    ) -> tuple[dict[str, Any], LLMUsage]:
        raise NotImplementedError

