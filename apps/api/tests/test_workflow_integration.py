from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.enums import MeetingType, TaskStatus
from app.db.base import Base
from app.models import MeetingTask
from app.services.memory import write_confirmed_memory
from app.services.seed import seed_demo_data
from app.services.workflow import WorkflowRunner


@pytest.mark.asyncio
async def test_mock_workflow_reaches_confirmation_and_memory_write() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    seed_demo_data(db)

    task = MeetingTask(
        lab_id="lab_demo",
        project_id="project_agent",
        meeting_type=MeetingType.PROJECT_REPORT.value,
        meeting_date=date(2026, 6, 30),
        raw_transcript="\n".join(
            [
                "[00:00:03] 发言人1: 今天先听张同学汇报。",
                "[00:00:15] 发言人2: 我这周完成了数据预处理。",
                "[00:01:10] 发言人1: 下周需要把实验日志整理成表格。",
                "[00:01:35] 发言人2: 下周计划完成消融实验。",
            ]
        ),
        speaker_mapping={"发言人1": "user_advisor", "发言人2": "user_alice"},
    )
    db.add(task)
    db.commit()

    await WorkflowRunner(db=db, batch_size=2).run_task(task.task_id)
    db.refresh(task)

    assert task.task_status == TaskStatus.AWAITING_CONFIRMATION.value
    assert task.draft_result is not None
    assert task.confirmed_result is None

    task.confirmed_result = task.draft_result
    task.task_status = TaskStatus.CONFIRMED.value
    db.commit()
    counters = write_confirmed_memory(db, task=task)

    assert counters["project_memories"] == 1
    assert counters["student_profiles"] >= 1
    assert counters["action_trackers"] >= 1


def test_memory_write_resolves_display_names_from_extension_mapping() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    seed_demo_data(db)

    task = MeetingTask(
        lab_id="lab_demo",
        project_id="project_agent",
        meeting_type=MeetingType.PROJECT_REPORT.value,
        meeting_date=date(2026, 7, 1),
        raw_transcript="[00:00:03] 发言人2: 下周计划完成消融实验。",
        speaker_mapping={"发言人2": "张同学"},
        task_status=TaskStatus.CONFIRMED.value,
        confirmed_result={
            "meeting_type": "project_report",
            "per_student_reports": [
                {
                    "user_id": "张同学",
                    "display_name": "张同学",
                    "previous_commitments_review": [],
                    "this_week_completed": [],
                    "current_blockers": [],
                    "next_week_plan": [{"description": "下周计划完成消融实验", "target_date_if_mentioned": "下周"}],
                    "advisor_feedback": [],
                }
            ],
            "project_level_summary": {"overall_progress_note": "显示名解析测试", "cross_student_risk_signals": []},
        },
    )
    db.add(task)
    db.commit()

    counters = write_confirmed_memory(db, task=task)

    assert counters["student_profiles"] == 1
    assert counters["action_trackers"] == 1
