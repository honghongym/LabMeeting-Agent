from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ProjectResponse(BaseModel):
    project_id: str
    lab_id: str
    project_name: str
    description: str | None = None


class MemberResponse(BaseModel):
    user_id: str
    lab_id: str
    display_name: str
    role: str


class EvaluationTemplateResponse(BaseModel):
    template_id: str
    lab_id: str | None
    defense_subtype: str
    degree_type_applicable: str
    dimensions: list[dict[str, Any]]
    is_active: bool
    version: int


class EvaluationTemplateUpdateRequest(BaseModel):
    defense_subtype: str = Field(pattern="^(proposal|midterm|final)$")
    degree_type_applicable: str = "both"
    dimensions: list[dict[str, Any]]
    is_active: bool = True


class ActionTrackerResponse(BaseModel):
    action_id: str
    project_id: str
    user_id: str
    description: str
    expected_date: str | None
    status: str
    source_task_id: str

