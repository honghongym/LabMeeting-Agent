from __future__ import annotations

import asyncio

from celery import Celery

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.workflow import WorkflowRunner


celery_app = Celery("meeting_agent", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_routes = {"app.tasks.process_meeting_task": {"queue": "agent"}}


@celery_app.task(name="app.tasks.process_meeting_task")
def process_meeting_task(task_id: str) -> None:
    db = SessionLocal()
    try:
        asyncio.run(WorkflowRunner(db=db).run_task(task_id))
    finally:
        db.close()

