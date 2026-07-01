from __future__ import annotations

from collections import defaultdict
import re
from typing import Any

from app.agent.chunking import TranscriptChunk
from app.agent.transcript import parse_transcript
from app.core.enums import ConfidenceTendency, MeetingType
from app.llm.base import LLMProvider, LLMUsage, MapExtraction


class MockProvider(LLMProvider):
    async def extract_chunk(
        self,
        *,
        meeting_type: MeetingType,
        chunk: TranscriptChunk,
        schema_hint: dict[str, Any],
        rolling_state: dict[str, Any],
        historical_memory: list[dict[str, Any]],
    ) -> MapExtraction:
        turns = parse_transcript(chunk.raw_text)
        per_speaker: dict[str, list[str]] = defaultdict(list)
        for turn in turns:
            per_speaker[turn.speaker_label].append(turn.content)

        if meeting_type == MeetingType.LITERATURE_REVIEW:
            payload = self._literature_payload(chunk, per_speaker)
        elif meeting_type in {
            MeetingType.PROPOSAL_DEFENSE,
            MeetingType.MIDTERM_DEFENSE,
            MeetingType.FINAL_DEFENSE,
        }:
            payload = self._defense_payload(chunk, per_speaker, meeting_type)
        else:
            payload = self._project_payload(chunk, per_speaker)

        next_state = {
            "current_topic": self._guess_topic(chunk.raw_text),
            "recent_commitments": payload.get("commitments", [])[:5],
            "open_questions": payload.get("questions", [])[:5],
            "last_chunk_id": chunk.chunk_id,
        }
        usage = LLMUsage(
            prompt_tokens=max(1, int(len(chunk.raw_text) / 1.7)),
            completion_tokens=max(80, int(len(str(payload)) / 2.5)),
        )
        return MapExtraction(chunk_id=chunk.chunk_id, payload=payload, rolling_state=next_state, usage=usage)

    async def reduce(
        self,
        *,
        meeting_type: MeetingType,
        map_results: list[MapExtraction],
        historical_memory: list[dict[str, Any]],
        speaker_mapping: dict[str, str],
    ) -> tuple[dict[str, Any], LLMUsage]:
        if meeting_type == MeetingType.LITERATURE_REVIEW:
            result = self._reduce_literature(map_results, historical_memory, speaker_mapping)
        elif meeting_type in {
            MeetingType.PROPOSAL_DEFENSE,
            MeetingType.MIDTERM_DEFENSE,
            MeetingType.FINAL_DEFENSE,
        }:
            result = self._reduce_defense(meeting_type, map_results, historical_memory, speaker_mapping)
        else:
            result = self._reduce_project(map_results, historical_memory, speaker_mapping)

        usage = LLMUsage(prompt_tokens=max(120, len(str(map_results)) // 3), completion_tokens=max(160, len(str(result)) // 3))
        return result, usage

    def _project_payload(self, chunk: TranscriptChunk, per_speaker: dict[str, list[str]]) -> dict[str, Any]:
        reports = []
        commitments = []
        questions = []
        for speaker, texts in per_speaker.items():
            joined = " ".join(texts)
            completed = self._sentences_with(joined, ("完成", "做了", "实现", "处理"))
            blockers = self._sentences_with(joined, ("问题", "卡", "困难", "风险", "阻塞"))
            plans = self._sentences_with(joined, ("下周", "接下来", "计划", "准备"))
            feedback = self._sentences_with(joined, ("建议", "需要", "注意", "可以"))
            for plan in plans:
                commitments.append({"speaker_label": speaker, "description": plan, "evidence_quote_ref": chunk.chunk_id})
            for question in self._sentences_with(joined, ("?", "？", "怎么样", "为什么")):
                questions.append({"speaker_label": speaker, "question": question})
            reports.append(
                {
                    "speaker_label": speaker,
                    "completed": completed[:3],
                    "blockers": blockers[:3],
                    "plans": plans[:3],
                    "advisor_feedback": feedback[:3],
                    "evidence_quote_ref": f"{chunk.chunk_id}:{chunk.start_time}",
                }
            )
        return {"kind": "project_report_map", "reports": reports, "commitments": commitments, "questions": questions}

    def _literature_payload(self, chunk: TranscriptChunk, per_speaker: dict[str, list[str]]) -> dict[str, Any]:
        raw = " ".join(" ".join(texts) for texts in per_speaker.values())
        title = self._extract_title(raw) or "未命名文献"
        return {
            "kind": "literature_review_map",
            "title": title,
            "method_summary": self._first_or_default(raw, ("方法", "模型", "框架"), "围绕论文核心方法进行了梳理。"),
            "innovation_points": self._sentences_with(raw, ("创新", "贡献", "优势"))[:3],
            "qa": self._sentences_with(raw, ("?", "？", "为什么", "如何"))[:4],
            "duplication_check_needed": True,
            "presenter_label": next(iter(per_speaker.keys()), "发言人"),
            "evidence_quote_ref": f"{chunk.chunk_id}:{chunk.start_time}",
        }

    def _defense_payload(
        self,
        chunk: TranscriptChunk,
        per_speaker: dict[str, list[str]],
        meeting_type: MeetingType,
    ) -> dict[str, Any]:
        raw = " ".join(" ".join(texts) for texts in per_speaker.values())
        return {
            "kind": "defense_evaluation_map",
            "candidate_label": next(iter(per_speaker.keys()), "发言人"),
            "dimension_evidence": [
                {
                    "dimension_name": "研究方案可行性",
                    "evidence_excerpts": [
                        {
                            "content_summary": self._first_or_default(raw, ("方案", "实验", "路线"), "本片段提到了研究方案或实验安排。"),
                            "evidence_quote_ref": f"{chunk.chunk_id}:{chunk.start_time}",
                        }
                    ],
                    "confidence_tendency": ConfidenceTendency.MODERATE_SUPPORT.value,
                    "note": "Mock 模式基于关键词生成倾向性评估，仅用于流程演示。",
                }
            ],
            "qa": self._sentences_with(raw, ("?", "？", "为什么", "如何", "解释"))[:4],
            "meeting_type": meeting_type.value,
        }

    def _reduce_project(
        self,
        map_results: list[MapExtraction],
        historical_memory: list[dict[str, Any]],
        speaker_mapping: dict[str, str],
    ) -> dict[str, Any]:
        grouped: dict[str, dict[str, Any]] = {}
        for result in map_results:
            for report in result.payload.get("reports", []):
                label = report["speaker_label"]
                person = grouped.setdefault(
                    label,
                    {
                        "user_id": speaker_mapping.get(label, label),
                        "display_name": speaker_mapping.get(label, label),
                        "previous_commitments_review": [],
                        "this_week_completed": [],
                        "current_blockers": [],
                        "next_week_plan": [],
                        "advisor_feedback": [],
                    },
                )
                person["this_week_completed"].extend(
                    {"description": item, "evidence_quote_ref": report["evidence_quote_ref"]}
                    for item in report.get("completed", [])
                )
                person["current_blockers"].extend(
                    {"description": item, "mentioned_severity": "medium"} for item in report.get("blockers", [])
                )
                person["next_week_plan"].extend(
                    {"description": item, "target_date_if_mentioned": "下周"} for item in report.get("plans", [])
                )
                person["advisor_feedback"].extend(
                    {"feedback_content": item, "related_to_which_item": "本次汇报"} for item in report.get("advisor_feedback", [])
                )

        for memory in historical_memory:
            label = memory.get("speaker_label") or memory.get("user_id")
            if label in grouped:
                grouped[label]["previous_commitments_review"].append(
                    {
                        "commitment_description": memory.get("description", "历史承诺"),
                        "expected_date": memory.get("expected_date"),
                        "current_status": memory.get("status", "open"),
                        "evidence_quote_ref": memory.get("source_task_id", "history"),
                    }
                )

        return {
            "meeting_type": MeetingType.PROJECT_REPORT.value,
            "participants": [
                {"user_id": value, "display_name": value, "attended": True}
                for value in sorted(set(speaker_mapping.values()) or set(grouped.keys()))
            ],
            "per_student_reports": list(grouped.values()),
            "project_level_summary": {
                "overall_progress_note": "本次组会已按学生聚合完成进展、阻塞点、下周计划和导师反馈。",
                "cross_student_risk_signals": self._risk_signals(list(grouped.values())),
            },
        }

    def _reduce_literature(
        self,
        map_results: list[MapExtraction],
        historical_memory: list[dict[str, Any]],
        speaker_mapping: dict[str, str],
    ) -> dict[str, Any]:
        first = map_results[0].payload if map_results else {}
        title = first.get("title", "未命名文献")
        similar = [
            memory
            for memory in historical_memory
            if title != "未命名文献" and title.lower() in str(memory.get("title", "")).lower()
        ]
        return {
            "meeting_type": MeetingType.LITERATURE_REVIEW.value,
            "presenter": {
                "user_id": speaker_mapping.get(first.get("presenter_label", ""), first.get("presenter_label", "unknown")),
                "display_name": speaker_mapping.get(first.get("presenter_label", ""), first.get("presenter_label", "未知汇报人")),
            },
            "literature_info": {
                "title": title,
                "authors_if_mentioned": None,
                "venue_if_mentioned": None,
                "core_method_summary": first.get("method_summary", "已提取核心方法摘要。"),
                "innovation_points": _unique_flatten(result.payload.get("innovation_points", []) for result in map_results),
                "relation_to_existing_work": "存在历史相似记录。" if similar else "暂无结构化历史重复记录。",
            },
            "comprehension_assessment": {
                "depth_indicator": "moderate",
                "supporting_evidence": [
                    {"qa_exchange_summary": item, "evidence_quote_ref": result.payload.get("evidence_quote_ref")}
                    for result in map_results
                    for item in result.payload.get("qa", [])
                ],
            },
            "advisor_qa_log": [
                {"question": item, "response_summary": "Mock 模式提取的问答摘要", "advisor_followup_comment": None}
                for result in map_results
                for item in result.payload.get("qa", [])
            ],
            "duplication_check_needed": True,
            "duplication_insight": "发现组内相似文献记录。" if similar else "未发现明显重复精读记录。",
        }

    def _reduce_defense(
        self,
        meeting_type: MeetingType,
        map_results: list[MapExtraction],
        historical_memory: list[dict[str, Any]],
        speaker_mapping: dict[str, str],
    ) -> dict[str, Any]:
        first = map_results[0].payload if map_results else {}
        candidate_label = first.get("candidate_label", "candidate")
        dimensions = []
        for result in map_results:
            dimensions.extend(result.payload.get("dimension_evidence", []))
        return {
            "meeting_type": meeting_type.value,
            "candidate": {
                "user_id": speaker_mapping.get(candidate_label, candidate_label),
                "display_name": speaker_mapping.get(candidate_label, candidate_label),
                "degree_type": "master",
                "enrollment_year": "2024",
            },
            "evaluation_dimensions": dimensions
            or [
                {
                    "dimension_name": "研究方案可行性",
                    "evidence_excerpts": [],
                    "confidence_tendency": ConfidenceTendency.INSUFFICIENT_EVIDENCE.value,
                    "note": "当前转录未提供足够证据。",
                }
            ],
            "qa_session_log": [
                {
                    "question": item,
                    "questioner_role": "advisor",
                    "candidate_response_summary": "Mock 模式汇总的回答摘要",
                    "response_quality_note": "证据部分支持",
                }
                for result in map_results
                for item in result.payload.get("qa", [])
            ],
            "comparison_with_history": {
                "previous_defense_questions_revisited": [
                    {
                        "previous_question": memory.get("question", "历史答辩问题"),
                        "was_addressed_this_time": False,
                        "note": "首版结构化检索已定位历史问题，需导师确认是否已回应。",
                    }
                    for memory in historical_memory[:3]
                ],
                "deviation_from_original_plan": "Mock 模式未发现明确计划偏差。",
            },
        }

    def _sentences_with(self, text: str, keywords: tuple[str, ...]) -> list[str]:
        fragments = re.split(r"[。！？!?；;]\s*", text)
        return [fragment.strip() for fragment in fragments if fragment.strip() and any(k in fragment for k in keywords)]

    def _first_or_default(self, text: str, keywords: tuple[str, ...], default: str) -> str:
        matches = self._sentences_with(text, keywords)
        return matches[0] if matches else default

    def _guess_topic(self, text: str) -> str:
        if "文献" in text or "论文" in text:
            return "文献精读"
        if "答辩" in text or "开题" in text or "中期" in text:
            return "答辩评估"
        return "项目进展"

    def _extract_title(self, text: str) -> str | None:
        match = re.search(r"《([^》]+)》", text)
        if match:
            return match.group(1)
        match = re.search(r"论文\s*([A-Za-z0-9\u4e00-\u9fff :：-]{4,40})", text)
        return match.group(1).strip() if match else None

    def _risk_signals(self, reports: list[dict[str, Any]]) -> list[str]:
        risks = []
        blockers = sum(len(report.get("current_blockers", [])) for report in reports)
        if blockers:
            risks.append(f"共有 {blockers} 个阻塞点需要会后跟踪。")
        overdue = sum(len(report.get("previous_commitments_review", [])) for report in reports)
        if overdue:
            risks.append(f"有 {overdue} 条历史承诺需要复盘状态。")
        return risks


def _unique_flatten(groups: Any) -> list[str]:
    seen = set()
    result = []
    for group in groups:
        for item in group:
            if item not in seen:
                seen.add(item)
                result.append(item)
    return result

