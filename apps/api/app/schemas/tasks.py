from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.enums import MeetingType, TaskStatus


class TaskCreateRequest(BaseModel):
    lab_id: str = Field(default="lab_demo")
    project_id: str = Field(default="project_agent")
    meeting_type: MeetingType = Field(default=MeetingType.PROJECT_REPORT)
    llm_provider: Literal["mock", "tongyi"] | None = Field(
        default=None,
        description="Per-task LLM mode. Defaults to server LLM_PROVIDER when omitted.",
    )
    meeting_date: date
    raw_transcript: str = Field(min_length=20)
    speaker_mapping: dict[str, str] = Field(default_factory=dict)


class TaskCreateResponse(BaseModel):
    task_id: str
    task_status: TaskStatus
    llm_provider: Literal["mock", "tongyi"]


class TaskStatusResponse(BaseModel):
    task_id: str
    task_status: TaskStatus
    total_chunks: int
    completed_chunks: int
    progress_percent: int
    progress_message: str | None = None
    token_consumed: int = 0
    degraded_reason: str | None = None
    error_message: str | None = None


class TaskDraftResponse(BaseModel):
    task_id: str
    task_status: TaskStatus
    draft_result: dict[str, Any] | None


class ConfirmationEditInput(BaseModel):
    field_path: str
    original_value: Any | None = None
    corrected_value: Any | None = None
    edit_type: str = "other"


class TaskConfirmRequest(BaseModel):
    confirmed_result: dict[str, Any]
    edits: list[ConfirmationEditInput] = Field(default_factory=list)
    edited_by: str = "user_advisor"


class TaskConfirmResponse(BaseModel):
    task_id: str
    task_status: TaskStatus
    memory_write_summary: dict[str, int]


class ReportResponse(BaseModel):
    task_id: str
    role: str
    meeting_type: MeetingType
    report: dict[str, Any]
