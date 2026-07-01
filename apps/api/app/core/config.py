from __future__ import annotations

from pydantic import BaseModel
import os


class Settings(BaseModel):
    app_name: str = "Graduate Meeting Minutes Agent"
    api_prefix: str = "/api"
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://agent:agent@postgres:5432/meeting_agent",
    )
    redis_url: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    cors_origins: list[str] = ["http://localhost:5173", "chrome-extension://*"]
    llm_provider: str = os.getenv("LLM_PROVIDER", "mock")
    sync_tasks: bool = os.getenv("SYNC_TASKS", "false").lower() == "true"
    default_lab_id: str = "lab_demo"
    default_user_id: str = "user_advisor"


settings = Settings()

