from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.agent.budget import TokenBudgetController
from app.agent.chunking import chunk_transcript
from app.agent.transcript import parse_transcript
from app.agent.validation import assert_no_binary_defense_judgement, validate_confidence_tendency
from app.core.enums import MeetingType, TaskStatus
from app.llm.base import LLMProvider, MapExtraction
from app.llm.factory import get_llm_provider
from app.models import MeetingTask
from app.services.memory import retrieve_historical_memory


class WorkflowRunner:
    def __init__(
        self,
        *,
        db: Session,
        provider: LLMProvider | None = None,
        budget: TokenBudgetController | None = None,
        batch_size: int = 4,
    ) -> None:
        self.db = db
        self.provider = provider or get_llm_provider()
        self.budget = budget or TokenBudgetController()
        self.batch_size = batch_size

    async def run_task(self, task_id: str) -> None:
        task = self.db.get(MeetingTask, task_id)
        if not task:
            return

        try:
            self._update(task, TaskStatus.SEGMENTING, 5, "正在解析转录文本并生成语义分段")
            turns = parse_transcript(task.raw_transcript)
            chunks = chunk_transcript(turns)
            task.total_chunks = len(chunks)
            self.db.commit()

            self._update(task, TaskStatus.EXTRACTING, 15, f"已生成 {len(chunks)} 个 Chunk，开始 Map 抽取")
            historical_memory = retrieve_historical_memory(self.db, task=task)
            map_results: list[MapExtraction] = []
            rolling_state: dict[str, Any] = {}
            consumed_tokens = 0

            for start in range(0, len(chunks), self.batch_size):
                batch = chunks[start : start + self.batch_size]
                calls = []
                for chunk in batch:
                    decision = self.budget.check_call(chunk.raw_text, str(historical_memory))
                    if not decision.allowed:
                        task.degraded_reason = decision.reason
                    consumed_tokens += decision.estimated_tokens
                    calls.append(
                        self.provider.extract_chunk(
                            meeting_type=MeetingType(task.meeting_type),
                            chunk=chunk,
                            schema_hint=self._schema_hint(MeetingType(task.meeting_type)),
                            rolling_state=rolling_state,
                            historical_memory=historical_memory,
                        )
                    )
                batch_results = await asyncio.gather(*calls)
                map_results.extend(batch_results)
                if batch_results:
                    rolling_state = batch_results[-1].rolling_state
                task.completed_chunks = len(map_results)
                progress = 15 + int((task.completed_chunks / max(1, task.total_chunks)) * 55)
                task.token_consumed = consumed_tokens + sum(
                    result.usage.prompt_tokens + result.usage.completion_tokens for result in map_results
                )
                task.progress_percent = min(progress, 70)
                task.progress_message = f"Map 阶段已完成 {task.completed_chunks}/{task.total_chunks} 个 Chunk"
                self.db.commit()

            self._update(task, TaskStatus.REDUCING, 78, "正在执行 Reduce 聚合与历史记忆比对")
            reduce_memory = [] if self.budget.should_degrade_reduce(task.token_consumed) else historical_memory
            if not reduce_memory and historical_memory:
                task.degraded_reason = task.degraded_reason or "reduce_history_lookup_skipped_by_budget"
            draft_result, reduce_usage = await self.provider.reduce(
                meeting_type=MeetingType(task.meeting_type),
                map_results=map_results,
                historical_memory=reduce_memory,
                speaker_mapping=task.speaker_mapping,
            )
            self._validate_result(MeetingType(task.meeting_type), draft_result)

            task.draft_result = draft_result
            task.token_consumed += reduce_usage.prompt_tokens + reduce_usage.completion_tokens
            self._update(task, TaskStatus.AWAITING_CONFIRMATION, 92, "草稿已生成，等待人工确认")
        except Exception as exc:  # pragma: no cover - integration safety net
            task.task_status = TaskStatus.FAILED.value
            task.error_message = str(exc)
            task.progress_message = "处理失败"
            task.updated_at = datetime.utcnow()
            self.db.commit()

    def _update(self, task: MeetingTask, status: TaskStatus, progress: int, message: str) -> None:
        task.task_status = status.value
        task.progress_percent = progress
        task.progress_message = message
        task.updated_at = datetime.utcnow()
        self.db.commit()

    def _schema_hint(self, meeting_type: MeetingType) -> dict[str, Any]:
        if meeting_type == MeetingType.LITERATURE_REVIEW:
            return {"schema": "LiteratureReviewSchema"}
        if meeting_type in {MeetingType.PROPOSAL_DEFENSE, MeetingType.MIDTERM_DEFENSE, MeetingType.FINAL_DEFENSE}:
            return {"schema": "DefenseEvaluationSchema"}
        return {"schema": "ProjectReportSchema"}

    def _validate_result(self, meeting_type: MeetingType, result: dict[str, Any]) -> None:
        if meeting_type not in {
            MeetingType.PROPOSAL_DEFENSE,
            MeetingType.MIDTERM_DEFENSE,
            MeetingType.FINAL_DEFENSE,
        }:
            if meeting_type == MeetingType.PROJECT_REPORT and "per_student_reports" not in result:
                raise ValueError("LLM result missing required key: per_student_reports")
            if meeting_type == MeetingType.LITERATURE_REVIEW and "literature_info" not in result:
                raise ValueError("LLM result missing required key: literature_info")
            return

        if "evaluation_dimensions" not in result:
            raise ValueError("LLM result missing required key: evaluation_dimensions")
        assert_no_binary_defense_judgement(str(result))
        for dimension in result.get("evaluation_dimensions", []):
            validate_confidence_tendency(dimension.get("confidence_tendency", ""))
