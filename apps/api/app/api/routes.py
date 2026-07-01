from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import MeetingType, TaskStatus
from app.db.session import get_db
from app.models import ActionTracker, ConfirmationEdit, EvaluationTemplate, MeetingTask, Member, Project, ProjectMember
from app.schemas.domain import (
    ActionTrackerResponse,
    EvaluationTemplateResponse,
    EvaluationTemplateUpdateRequest,
    MemberResponse,
    ProjectResponse,
)
from app.schemas.tasks import (
    TaskConfirmRequest,
    TaskConfirmResponse,
    TaskCreateRequest,
    TaskCreateResponse,
    TaskDraftResponse,
    TaskStatusResponse,
    ReportResponse,
)
from app.services.memory import write_confirmed_memory
from app.services.reporting import build_report
from app.services.workflow import WorkflowRunner
from app.tasks import process_meeting_task


router = APIRouter()


@router.post("/tasks", response_model=TaskCreateResponse)
async def create_task(payload: TaskCreateRequest, db: Annotated[Session, Depends(get_db)]) -> TaskCreateResponse:
    project = db.get(Project, payload.project_id)
    if not project or project.lab_id != payload.lab_id:
        raise HTTPException(status_code=404, detail="Project not found in lab")

    task = MeetingTask(
        lab_id=payload.lab_id,
        project_id=payload.project_id,
        meeting_type=payload.meeting_type.value,
        meeting_date=payload.meeting_date,
        raw_transcript=payload.raw_transcript,
        speaker_mapping=payload.speaker_mapping,
        task_status=TaskStatus.QUEUED.value,
        progress_message="任务已入队",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    if settings.sync_tasks:
        await WorkflowRunner(db=db).run_task(task.task_id)
    else:
        process_meeting_task.delay(task.task_id)

    return TaskCreateResponse(task_id=task.task_id, task_status=TaskStatus(task.task_status))


@router.get("/tasks/{task_id}/status", response_model=TaskStatusResponse)
def get_task_status(task_id: str, db: Annotated[Session, Depends(get_db)]) -> TaskStatusResponse:
    task = _get_task(db, task_id)
    return TaskStatusResponse(
        task_id=task.task_id,
        task_status=TaskStatus(task.task_status),
        total_chunks=task.total_chunks,
        completed_chunks=task.completed_chunks,
        progress_percent=task.progress_percent,
        progress_message=task.progress_message,
        token_consumed=task.token_consumed,
        degraded_reason=task.degraded_reason,
        error_message=task.error_message,
    )


@router.get("/tasks/{task_id}/draft", response_model=TaskDraftResponse)
def get_task_draft(task_id: str, db: Annotated[Session, Depends(get_db)]) -> TaskDraftResponse:
    task = _get_task(db, task_id)
    return TaskDraftResponse(
        task_id=task.task_id,
        task_status=TaskStatus(task.task_status),
        draft_result=task.draft_result,
    )


@router.post("/tasks/{task_id}/confirm", response_model=TaskConfirmResponse)
def confirm_task(task_id: str, payload: TaskConfirmRequest, db: Annotated[Session, Depends(get_db)]) -> TaskConfirmResponse:
    task = _get_task(db, task_id)
    if task.task_status != TaskStatus.AWAITING_CONFIRMATION.value:
        raise HTTPException(status_code=409, detail="Only awaiting_confirmation tasks can be confirmed")

    task.confirmed_result = payload.confirmed_result
    task.task_status = TaskStatus.CONFIRMED.value
    task.progress_percent = 100
    task.progress_message = "已确认归档并写入长期记忆"
    task.confirmed_at = datetime.utcnow()
    for edit in payload.edits:
        db.add(
            ConfirmationEdit(
                task_id=task.task_id,
                field_path=edit.field_path,
                original_value=str(edit.original_value) if edit.original_value is not None else None,
                corrected_value=str(edit.corrected_value) if edit.corrected_value is not None else None,
                edited_by=payload.edited_by,
                edit_type=edit.edit_type,
            )
        )
    db.commit()
    db.refresh(task)
    summary = write_confirmed_memory(db, task=task)
    return TaskConfirmResponse(task_id=task.task_id, task_status=TaskStatus.CONFIRMED, memory_write_summary=summary)


@router.get("/tasks/{task_id}/report", response_model=ReportResponse)
def get_task_report(
    task_id: str,
    db: Annotated[Session, Depends(get_db)],
    role: Annotated[str, Query(pattern="^(advisor|student)$")] = "advisor",
) -> ReportResponse:
    task = _get_task(db, task_id)
    if task.task_status != TaskStatus.CONFIRMED.value or not task.confirmed_result:
        raise HTTPException(status_code=409, detail="Report is available only after confirmation")
    meeting_type = MeetingType(task.meeting_type)
    return ReportResponse(
        task_id=task.task_id,
        role=role,
        meeting_type=meeting_type,
        report=build_report(confirmed_result=task.confirmed_result, meeting_type=meeting_type, role=role),
    )


@router.get("/labs/{lab_id}/projects", response_model=list[ProjectResponse])
def list_projects(lab_id: str, db: Annotated[Session, Depends(get_db)]) -> list[ProjectResponse]:
    rows = db.execute(select(Project).where(Project.lab_id == lab_id)).scalars().all()
    return [ProjectResponse(project_id=row.project_id, lab_id=row.lab_id, project_name=row.project_name, description=row.description) for row in rows]


@router.get("/projects/{project_id}/members", response_model=list[MemberResponse])
def list_project_members(project_id: str, db: Annotated[Session, Depends(get_db)]) -> list[MemberResponse]:
    rows = db.execute(
        select(Member).join(ProjectMember, ProjectMember.user_id == Member.user_id).where(ProjectMember.project_id == project_id)
    ).scalars().all()
    return [MemberResponse(user_id=row.user_id, lab_id=row.lab_id, display_name=row.display_name, role=row.role) for row in rows]


@router.get("/labs/{lab_id}/eval-templates", response_model=list[EvaluationTemplateResponse])
def get_eval_templates(lab_id: str, db: Annotated[Session, Depends(get_db)]) -> list[EvaluationTemplateResponse]:
    rows = db.execute(
        select(EvaluationTemplate).where(
            EvaluationTemplate.is_active.is_(True),
            or_(EvaluationTemplate.lab_id == lab_id, EvaluationTemplate.lab_id.is_(None)),
        )
    ).scalars().all()
    return [
        EvaluationTemplateResponse(
            template_id=row.template_id,
            lab_id=row.lab_id,
            defense_subtype=row.defense_subtype,
            degree_type_applicable=row.degree_type_applicable,
            dimensions=row.dimensions,
            is_active=row.is_active,
            version=row.version,
        )
        for row in rows
    ]


@router.put("/labs/{lab_id}/eval-templates", response_model=EvaluationTemplateResponse)
def upsert_eval_template(
    lab_id: str,
    payload: EvaluationTemplateUpdateRequest,
    db: Annotated[Session, Depends(get_db)],
) -> EvaluationTemplateResponse:
    existing = db.execute(
        select(EvaluationTemplate).where(
            EvaluationTemplate.lab_id == lab_id,
            EvaluationTemplate.defense_subtype == payload.defense_subtype,
            EvaluationTemplate.degree_type_applicable == payload.degree_type_applicable,
        )
    ).scalar_one_or_none()
    if existing:
        existing.dimensions = payload.dimensions
        existing.is_active = payload.is_active
        existing.version += 1
        row = existing
    else:
        row = EvaluationTemplate(
            lab_id=lab_id,
            defense_subtype=payload.defense_subtype,
            degree_type_applicable=payload.degree_type_applicable,
            dimensions=payload.dimensions,
            is_active=payload.is_active,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return EvaluationTemplateResponse(
        template_id=row.template_id,
        lab_id=row.lab_id,
        defense_subtype=row.defense_subtype,
        degree_type_applicable=row.degree_type_applicable,
        dimensions=row.dimensions,
        is_active=row.is_active,
        version=row.version,
    )


@router.get("/projects/{project_id}/action-tracker", response_model=list[ActionTrackerResponse])
def list_action_tracker(project_id: str, db: Annotated[Session, Depends(get_db)]) -> list[ActionTrackerResponse]:
    rows = db.execute(
        select(ActionTracker).where(
            ActionTracker.project_id == project_id,
            ActionTracker.status.in_(["open", "overdue"]),
        )
    ).scalars().all()
    return [
        ActionTrackerResponse(
            action_id=row.action_id,
            project_id=row.project_id,
            user_id=row.user_id,
            description=row.description,
            expected_date=row.expected_date,
            status=row.status,
            source_task_id=row.source_task_id,
        )
        for row in rows
    ]


def _get_task(db: Session, task_id: str) -> MeetingTask:
    task = db.get(MeetingTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task
