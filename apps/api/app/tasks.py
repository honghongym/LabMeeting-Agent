from __future__ import annotations

import asyncio

from celery import Celery

from app.core.config import settings
from app.db.session import SessionLocal
from app.llm.factory import get_llm_provider
from app.services.workflow import WorkflowRunner


celery_app = Celery("meeting_agent", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.task_routes = {"app.tasks.process_meeting_task": {"queue": "agent"}}


@celery_app.task(name="app.tasks.process_meeting_task")
def process_meeting_task(task_id: str, llm_provider: str | None = None) -> None:
    db = SessionLocal()
    try:
        provider = get_llm_provider(llm_provider) if llm_provider else None
        asyncio.run(WorkflowRunner(db=db, provider=provider).run_task(task_id))
    finally:
        db.close()
