from __future__ import annotations

import asyncio
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.agent.chunking import TranscriptChunk
from app.core.enums import MeetingType
from app.llm.base import LLMProvider, LLMUsage, MapExtraction
from app.llm.mock import MockProvider


class TongyiProvider(LLMProvider):
    """Tongyi OpenAI-compatible adapter with a mock fallback for open-source demos.

    The public repo can run without credentials. When DASHSCOPE_API_KEY is set,
    this class is the single integration point to replace the fallback with
    DashScope/Qwen structured output calls.
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        self.base_url = os.getenv(
            "DASHSCOPE_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        )
        self.model = os.getenv("DASHSCOPE_MODEL", "qwen-plus")
        self.fallback = MockProvider()

    async def extract_chunk(
        self,
        *,
        meeting_type: MeetingType,
        chunk: TranscriptChunk,
        schema_hint: dict[str, Any],
        rolling_state: dict[str, Any],
        historical_memory: list[dict[str, Any]],
    ) -> MapExtraction:
        if not self.api_key:
            return await self.fallback.extract_chunk(
                meeting_type=meeting_type,
                chunk=chunk,
                schema_hint=schema_hint,
                rolling_state=rolling_state,
                historical_memory=historical_memory,
            )
        prompt = {
            "task": "extract_meeting_chunk",
            "meeting_type": meeting_type.value,
            "schema_hint": schema_hint,
            "rolling_state": rolling_state,
            "historical_memory": historical_memory[:8],
            "chunk": {
                "chunk_id": chunk.chunk_id,
                "start_time": chunk.start_time,
                "end_time": chunk.end_time,
                "primary_speakers": chunk.primary_speakers,
                "raw_text": chunk.raw_text,
            },
            "output_contract": {
                "payload": "structured extraction JSON for this chunk",
                "rolling_state": "compact JSON memory for the next batch",
            },
        }
        content, usage = await self._chat_json(prompt)
        return MapExtraction(
            chunk_id=chunk.chunk_id,
            payload=content.get("payload", content),
            rolling_state=content.get("rolling_state", {}),
            usage=usage,
        )

    async def reduce(
        self,
        *,
        meeting_type: MeetingType,
        map_results: list[MapExtraction],
        historical_memory: list[dict[str, Any]],
        speaker_mapping: dict[str, str],
    ) -> tuple[dict[str, Any], LLMUsage]:
        if not self.api_key:
            return await self.fallback.reduce(
                meeting_type=meeting_type,
                map_results=map_results,
                historical_memory=historical_memory,
                speaker_mapping=speaker_mapping,
            )
        prompt = {
            "task": "reduce_meeting_extractions",
            "meeting_type": meeting_type.value,
            "map_results": [
                {"chunk_id": result.chunk_id, "payload": result.payload, "rolling_state": result.rolling_state}
                for result in map_results
            ],
            "historical_memory": historical_memory[:12],
            "speaker_mapping": speaker_mapping,
            "output_contract": "Return the final schema JSON only. Do not include markdown fences.",
        }
        return await self._chat_json(prompt)

    async def _chat_json(self, prompt: dict[str, Any]) -> tuple[dict[str, Any], LLMUsage]:
        return await asyncio.to_thread(self._chat_json_sync, prompt)

    def _chat_json_sync(self, prompt: dict[str, Any]) -> tuple[dict[str, Any], LLMUsage]:
        body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a structured extraction engine for graduate meeting transcripts. "
                        "Return valid JSON only. Avoid pass/fail or approval judgements for defense evaluation."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
        }
        request = Request(
            self.base_url,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=60) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Tongyi API HTTP {exc.code}: {detail}") from exc
        except URLError as exc:
            raise RuntimeError(f"Tongyi API request failed: {exc.reason}") from exc

        data = json.loads(raw)
        message = data["choices"][0]["message"]["content"]
        parsed = json.loads(message)
        usage_data = data.get("usage") or {}
        usage = LLMUsage(
            prompt_tokens=int(usage_data.get("prompt_tokens") or 0),
            completion_tokens=int(usage_data.get("completion_tokens") or 0),
        )
        return parsed, usage
