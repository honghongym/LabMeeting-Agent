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


class TongyiProvider(LLMProvider):
    """Tongyi OpenAI-compatible adapter.

    The public repo defaults to MockProvider. When a task explicitly selects
    Tongyi, this class is the integration point for DashScope/Qwen structured
    output calls.
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv(
            "DASHSCOPE_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        )
        self.model = os.getenv("DASHSCOPE_MODEL", "qwen-plus")

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
            raise RuntimeError("Tongyi provider requires DASHSCOPE_API_KEY or OPENAI_API_KEY")
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
            "output_contract": self._map_contract(meeting_type),
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
            raise RuntimeError("Tongyi provider requires DASHSCOPE_API_KEY or OPENAI_API_KEY")
        prompt = {
            "task": "reduce_meeting_extractions",
            "meeting_type": meeting_type.value,
            "map_results": [
                {"chunk_id": result.chunk_id, "payload": result.payload, "rolling_state": result.rolling_state}
                for result in map_results
            ],
            "historical_memory": historical_memory[:12],
            "speaker_mapping": speaker_mapping,
            "output_contract": self._reduce_contract(meeting_type),
        }
        content, usage = await self._chat_json(prompt)
        return self._unwrap_final_result(content), usage

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
        parsed = self._parse_json_content(message)
        usage_data = data.get("usage") or {}
        usage = LLMUsage(
            prompt_tokens=int(usage_data.get("prompt_tokens") or 0),
            completion_tokens=int(usage_data.get("completion_tokens") or 0),
        )
        return parsed, usage

    def _parse_json_content(self, content: Any) -> dict[str, Any]:
        if isinstance(content, dict):
            return content
        text = str(content).strip()
        if text.startswith("```"):
            text = text.strip("`").strip()
            if text.lower().startswith("json"):
                text = text[4:].strip()
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            raise ValueError("Tongyi response must be a JSON object")
        return parsed

    def _unwrap_final_result(self, content: dict[str, Any]) -> dict[str, Any]:
        for key in ("draft_result", "final_result", "result", "payload"):
            value = content.get(key)
            if isinstance(value, dict):
                return value
        return content

    def _map_contract(self, meeting_type: MeetingType) -> dict[str, Any]:
        if meeting_type == MeetingType.LITERATURE_REVIEW:
            payload = {
                "kind": "literature_review_map",
                "title": "paper title or 未命名文献",
                "method_summary": "core method summary",
                "innovation_points": ["short point"],
                "qa": ["question and answer summary"],
                "duplication_check_needed": True,
                "presenter_label": "speaker label from transcript",
                "evidence_quote_ref": "chunk_id:start_time",
            }
        elif meeting_type in {MeetingType.PROPOSAL_DEFENSE, MeetingType.MIDTERM_DEFENSE, MeetingType.FINAL_DEFENSE}:
            payload = {
                "kind": "defense_evaluation_map",
                "candidate_label": "speaker label",
                "dimension_evidence": [
                    {
                        "dimension_name": "研究方案可行性",
                        "evidence_excerpts": [
                            {"content_summary": "evidence summary", "evidence_quote_ref": "chunk_id:start_time"}
                        ],
                        "confidence_tendency": "moderate_support",
                        "note": "evidence-based note without pass/fail judgement",
                    }
                ],
                "qa": ["question and answer summary"],
                "meeting_type": meeting_type.value,
            }
        else:
            payload = {
                "kind": "project_report_map",
                "reports": [
                    {
                        "speaker_label": "speaker label",
                        "completed": ["completed work"],
                        "blockers": ["risk or blocker"],
                        "plans": ["next plan"],
                        "advisor_feedback": ["advisor feedback"],
                        "evidence_quote_ref": "chunk_id:start_time",
                    }
                ],
                "commitments": [
                    {"speaker_label": "speaker label", "description": "commitment", "evidence_quote_ref": "chunk_id"}
                ],
                "questions": [{"speaker_label": "speaker label", "question": "question"}],
            }
        return {
            "format": "Return valid JSON only. Do not include markdown fences.",
            "required_top_level_keys": ["payload", "rolling_state"],
            "payload_schema": payload,
            "rolling_state_schema": {
                "current_topic": "compact topic",
                "recent_commitments": ["short commitment"],
                "open_questions": ["short question"],
                "last_chunk_id": "chunk id",
            },
        }

    def _reduce_contract(self, meeting_type: MeetingType) -> dict[str, Any]:
        if meeting_type == MeetingType.LITERATURE_REVIEW:
            schema = {
                "meeting_type": "literature_review",
                "presenter": {"user_id": "mapped speaker value", "display_name": "mapped speaker value"},
                "literature_info": {
                    "title": "paper title",
                    "authors_if_mentioned": None,
                    "venue_if_mentioned": None,
                    "core_method_summary": "method summary",
                    "innovation_points": ["point"],
                    "relation_to_existing_work": "history comparison",
                },
                "comprehension_assessment": {
                    "depth_indicator": "shallow|moderate|deep",
                    "supporting_evidence": [
                        {"qa_exchange_summary": "QA summary", "evidence_quote_ref": "chunk ref"}
                    ],
                },
                "advisor_qa_log": [
                    {"question": "question", "response_summary": "answer summary", "advisor_followup_comment": None}
                ],
                "duplication_check_needed": True,
                "duplication_insight": "duplication insight",
            }
        elif meeting_type in {MeetingType.PROPOSAL_DEFENSE, MeetingType.MIDTERM_DEFENSE, MeetingType.FINAL_DEFENSE}:
            schema = {
                "meeting_type": meeting_type.value,
                "candidate": {
                    "user_id": "mapped speaker value",
                    "display_name": "mapped speaker value",
                    "degree_type": "master",
                    "enrollment_year": "2024",
                },
                "evaluation_dimensions": [
                    {
                        "dimension_name": "研究方案可行性",
                        "evidence_excerpts": [
                            {"content_summary": "evidence summary", "evidence_quote_ref": "chunk ref"}
                        ],
                        "confidence_tendency": "strong_support|moderate_support|insufficient_evidence|concern_raised",
                        "note": "evidence-based note; do not say pass or fail",
                    }
                ],
                "qa_session_log": [
                    {
                        "question": "question",
                        "questioner_role": "advisor",
                        "candidate_response_summary": "answer summary",
                        "response_quality_note": "evidence-based note",
                    }
                ],
                "comparison_with_history": {
                    "previous_defense_questions_revisited": [],
                    "deviation_from_original_plan": "history comparison",
                },
            }
        else:
            schema = {
                "meeting_type": "project_report",
                "participants": [{"user_id": "mapped speaker value", "display_name": "mapped speaker value", "attended": True}],
                "per_student_reports": [
                    {
                        "user_id": "mapped speaker value",
                        "display_name": "mapped speaker value",
                        "previous_commitments_review": [
                            {
                                "commitment_description": "historical commitment",
                                "expected_date": None,
                                "current_status": "open|done|overdue|unknown",
                                "evidence_quote_ref": "history ref",
                            }
                        ],
                        "this_week_completed": [{"description": "completed work", "evidence_quote_ref": "chunk ref"}],
                        "current_blockers": [{"description": "blocker", "mentioned_severity": "low|medium|high"}],
                        "next_week_plan": [{"description": "next plan", "target_date_if_mentioned": "下周"}],
                        "advisor_feedback": [
                            {"feedback_content": "advisor feedback", "related_to_which_item": "related item"}
                        ],
                    }
                ],
                "project_level_summary": {
                    "overall_progress_note": "overall summary",
                    "cross_student_risk_signals": ["risk"],
                },
            }
        return {
            "format": "Return this final schema JSON object only. Do not wrap it in another key.",
            "schema": schema,
            "constraints": [
                "Use speaker_mapping values for user_id and display_name when possible.",
                "Keep evidence summaries concise.",
                "For defense reports, never output pass/fail/通过/不通过 style judgements.",
            ],
        }
