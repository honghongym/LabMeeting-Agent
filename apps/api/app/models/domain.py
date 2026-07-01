from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import TaskStatus
from app.db.base import Base


def uuid_pk() -> str:
    return str(uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Lab(Base, TimestampMixin):
    __tablename__ = "labs"

    lab_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lab_name: Mapped[str] = mapped_column(String(200), nullable=False)
    institution: Mapped[str | None] = mapped_column(String(200))

    projects: Mapped[list["Project"]] = relationship(back_populates="lab")
    members: Mapped[list["Member"]] = relationship(back_populates="lab")


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    project_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lab_id: Mapped[str] = mapped_column(ForeignKey("labs.lab_id"), nullable=False, index=True)
    project_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    lab: Mapped["Lab"] = relationship(back_populates="projects")
    members: Mapped[list["ProjectMember"]] = relationship(back_populates="project")


class Member(Base, TimestampMixin):
    __tablename__ = "members"

    user_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    lab_id: Mapped[str] = mapped_column(ForeignKey("labs.lab_id"), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(40), nullable=False)

    lab: Mapped["Lab"] = relationship(back_populates="members")
    projects: Mapped[list["ProjectMember"]] = relationship(back_populates="member")


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (UniqueConstraint("project_id", "user_id", name="uq_project_member"),)

    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("members.user_id"), primary_key=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    project: Mapped["Project"] = relationship(back_populates="members")
    member: Mapped["Member"] = relationship(back_populates="projects")


class MeetingTask(Base, TimestampMixin):
    __tablename__ = "meeting_tasks"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_pk)
    lab_id: Mapped[str] = mapped_column(ForeignKey("labs.lab_id"), nullable=False, index=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False, index=True)
    meeting_type: Mapped[str] = mapped_column(String(40), nullable=False)
    meeting_date: Mapped[date] = mapped_column(Date, nullable=False)
    raw_transcript: Mapped[str] = mapped_column(Text, nullable=False)
    speaker_mapping: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    task_status: Mapped[str] = mapped_column(String(40), default=TaskStatus.QUEUED.value, nullable=False, index=True)
    total_chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_chunks: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    progress_message: Mapped[str | None] = mapped_column(String(300))
    draft_result: Mapped[dict | None] = mapped_column(JSON)
    confirmed_result: Mapped[dict | None] = mapped_column(JSON)
    token_consumed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    degraded_reason: Mapped[str | None] = mapped_column(String(200))
    error_message: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime)


class ConfirmationEdit(Base, TimestampMixin):
    __tablename__ = "confirmation_edits"

    edit_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_pk)
    task_id: Mapped[str] = mapped_column(ForeignKey("meeting_tasks.task_id"), nullable=False, index=True)
    field_path: Mapped[str] = mapped_column(String(300), nullable=False)
    original_value: Mapped[str | None] = mapped_column(Text)
    corrected_value: Mapped[str | None] = mapped_column(Text)
    edited_by: Mapped[str] = mapped_column(ForeignKey("members.user_id"), nullable=False)
    edit_type: Mapped[str] = mapped_column(String(80), nullable=False)


class ProjectMemory(Base, TimestampMixin):
    __tablename__ = "project_memories"

    memory_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_pk)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False, index=True)
    source_task_id: Mapped[str] = mapped_column(ForeignKey("meeting_tasks.task_id"), nullable=False, index=True)
    snapshot_date: Mapped[date] = mapped_column(Date, nullable=False)
    progress_summary: Mapped[str] = mapped_column(Text, nullable=False)
    risk_flags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    compression_level: Mapped[str] = mapped_column(String(40), default="full", nullable=False)


class StudentProfile(Base, TimestampMixin):
    __tablename__ = "student_profiles"

    profile_entry_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_pk)
    user_id: Mapped[str] = mapped_column(ForeignKey("members.user_id"), nullable=False, index=True)
    source_task_id: Mapped[str] = mapped_column(ForeignKey("meeting_tasks.task_id"), nullable=False, index=True)
    entry_type: Mapped[str] = mapped_column(String(80), nullable=False)
    content: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    compression_level: Mapped[str] = mapped_column(String(40), default="full", nullable=False)


class LiteratureMemory(Base, TimestampMixin):
    __tablename__ = "literature_memories"

    literature_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    lab_id: Mapped[str] = mapped_column(ForeignKey("labs.lab_id"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    method_summary: Mapped[str | None] = mapped_column(Text)
    read_by: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    related_projects: Mapped[list] = mapped_column(JSON, default=list, nullable=False)


class ActionTracker(Base, TimestampMixin):
    __tablename__ = "action_trackers"

    action_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_pk)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.project_id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("members.user_id"), nullable=False, index=True)
    source_task_id: Mapped[str] = mapped_column(ForeignKey("meeting_tasks.task_id"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    committed_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_date: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), default="open", nullable=False, index=True)
    resolved_task_id: Mapped[str | None] = mapped_column(ForeignKey("meeting_tasks.task_id"))


class EvaluationTemplate(Base, TimestampMixin):
    __tablename__ = "evaluation_templates"

    template_id: Mapped[str] = mapped_column(String(64), primary_key=True, default=uuid_pk)
    lab_id: Mapped[str | None] = mapped_column(ForeignKey("labs.lab_id"), index=True)
    defense_subtype: Mapped[str] = mapped_column(String(40), nullable=False)
    degree_type_applicable: Mapped[str] = mapped_column(String(20), default="both", nullable=False)
    dimensions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
