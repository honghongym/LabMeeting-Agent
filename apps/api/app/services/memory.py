from __future__ import annotations

from hashlib import sha1
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import MeetingType
from app.models import ActionTracker, LiteratureMemory, MeetingTask, Member, ProjectMemory, StudentProfile


def retrieve_historical_memory(db: Session, *, task: MeetingTask) -> list[dict[str, Any]]:
    meeting_type = MeetingType(task.meeting_type)
    speaker_values = _resolve_speaker_values(db, lab_id=task.lab_id, values=task.speaker_mapping.values())

    if meeting_type == MeetingType.PROJECT_REPORT:
        rows = db.execute(
            select(ActionTracker).where(
                ActionTracker.project_id == task.project_id,
                ActionTracker.status.in_(["open", "overdue"]),
            )
        ).scalars()
        return [
            {
                "action_id": row.action_id,
                "user_id": row.user_id,
                "description": row.description,
                "expected_date": row.expected_date,
                "status": row.status,
                "source_task_id": row.source_task_id,
            }
            for row in rows
            if not speaker_values or row.user_id in speaker_values
        ]

    if meeting_type == MeetingType.LITERATURE_REVIEW:
        rows = db.execute(select(LiteratureMemory).where(LiteratureMemory.lab_id == task.lab_id)).scalars()
        return [{"title": row.title, "method_summary": row.method_summary, "read_by": row.read_by} for row in rows]

    rows = db.execute(select(StudentProfile).where(StudentProfile.entry_type == "defense_feedback")).scalars()
    return [{"user_id": row.user_id, **row.content} for row in rows if not speaker_values or row.user_id in speaker_values]


def write_confirmed_memory(db: Session, *, task: MeetingTask) -> dict[str, int]:
    if not task.confirmed_result:
        return {"project_memories": 0, "student_profiles": 0, "literature_memories": 0, "action_trackers": 0}

    meeting_type = MeetingType(task.meeting_type)
    counters = {"project_memories": 0, "student_profiles": 0, "literature_memories": 0, "action_trackers": 0}
    result = task.confirmed_result

    if meeting_type == MeetingType.PROJECT_REPORT:
        summary = result.get("project_level_summary", {})
        db.add(
            ProjectMemory(
                project_id=task.project_id,
                source_task_id=task.task_id,
                snapshot_date=task.meeting_date,
                progress_summary=summary.get("overall_progress_note", "已归档项目汇报记忆。"),
                risk_flags=summary.get("cross_student_risk_signals", []),
                compression_level="full",
            )
        )
        counters["project_memories"] += 1
        for report in result.get("per_student_reports", []):
            user_id = _resolve_member_user_id(
                db,
                lab_id=task.lab_id,
                candidate=report.get("user_id") or report.get("display_name"),
            )
            if not user_id:
                continue
            db.add(
                StudentProfile(
                    user_id=user_id,
                    source_task_id=task.task_id,
                    entry_type="commitment_track",
                    content={"summary": report},
                    compression_level="full",
                )
            )
            counters["student_profiles"] += 1
            for plan in report.get("next_week_plan", []):
                description = plan.get("description")
                if not description:
                    continue
                db.add(
                    ActionTracker(
                        project_id=task.project_id,
                        user_id=user_id,
                        source_task_id=task.task_id,
                        description=description,
                        committed_date=task.meeting_date,
                        expected_date=plan.get("target_date_if_mentioned"),
                        status="open",
                    )
                )
                counters["action_trackers"] += 1

    elif meeting_type == MeetingType.LITERATURE_REVIEW:
        info = result.get("literature_info", {})
        title = info.get("title", "未命名文献")
        literature_id = sha1(f"{task.lab_id}:{title}".encode("utf-8")).hexdigest()
        existing = db.get(LiteratureMemory, literature_id)
        read_by = [{"user_id": result.get("presenter", {}).get("user_id"), "source_task_id": task.task_id}]
        if existing:
            existing.read_by = [*existing.read_by, *read_by]
            existing.method_summary = info.get("core_method_summary", existing.method_summary)
        else:
            db.add(
                LiteratureMemory(
                    literature_id=literature_id,
                    lab_id=task.lab_id,
                    title=title,
                    method_summary=info.get("core_method_summary"),
                    read_by=read_by,
                    related_projects=[task.project_id],
                )
            )
        counters["literature_memories"] += 1
        presenter = result.get("presenter", {})
        presenter_user_id = _resolve_member_user_id(
            db,
            lab_id=task.lab_id,
            candidate=presenter.get("user_id") or presenter.get("display_name"),
        )
        if presenter_user_id:
            db.add(
                StudentProfile(
                    user_id=presenter_user_id,
                    source_task_id=task.task_id,
                    entry_type="literature_breadth",
                    content=result,
                    compression_level="full",
                )
            )
            counters["student_profiles"] += 1

    else:
        candidate = result.get("candidate", {})
        candidate_user_id = _resolve_member_user_id(
            db,
            lab_id=task.lab_id,
            candidate=candidate.get("user_id") or candidate.get("display_name"),
        )
        if candidate_user_id:
            db.add(
                StudentProfile(
                    user_id=candidate_user_id,
                    source_task_id=task.task_id,
                    entry_type="defense_feedback",
                    content=result,
                    compression_level="full",
                )
            )
            counters["student_profiles"] += 1

    db.commit()
    return counters


def _resolve_speaker_values(db: Session, *, lab_id: str, values: Any) -> set[str]:
    resolved: set[str] = set()
    for value in values:
        user_id = _resolve_member_user_id(db, lab_id=lab_id, candidate=value)
        if user_id:
            resolved.add(user_id)
    return resolved


def _resolve_member_user_id(db: Session, *, lab_id: str, candidate: Any) -> str | None:
    """Accept either a real user_id or a display_name from the extension UI."""
    if not candidate:
        return None
    value = str(candidate).strip()
    member = db.execute(
        select(Member).where(
            Member.lab_id == lab_id,
            (Member.user_id == value) | (Member.display_name == value),
        )
    ).scalar_one_or_none()
    return member.user_id if member else None
