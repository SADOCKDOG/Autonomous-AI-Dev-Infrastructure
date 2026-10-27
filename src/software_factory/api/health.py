"""Endpoint de salud del backend."""

import sqlite3
from datetime import datetime, timezone
from fastapi import APIRouter
from pydantic import BaseModel
from software_factory import __version__
from software_factory.settings import settings
from software_factory.persistence.database import get_db

router = APIRouter(tags=["Health"])


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    database: str
    timestamp: str


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    db_status = "ok"
    try:
        with get_db() as conn:
            conn.execute("SELECT 1;").fetchone()
    except Exception as exc:
        db_status = f"unhealthy: {str(exc)}"

    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        version=__version__,
        environment=settings.factory_env,
        database=db_status,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
