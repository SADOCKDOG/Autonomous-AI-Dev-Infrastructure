"""Endpoint de salud del backend y del Model Gateway."""

from datetime import datetime, timezone
from fastapi import APIRouter
from pydantic import BaseModel
from software_factory import __version__
from software_factory.settings import settings
from software_factory.persistence.database import get_db
from software_factory.model_gateway.registry import ModelGateway
from software_factory.model_gateway.base import ProviderHealth

router = APIRouter(tags=["Health"])
gateway = ModelGateway()


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    database: str
    providers: dict[str, ProviderHealth]
    timestamp: str


@router.get("/health", response_model=HealthResponse)
async def get_health() -> HealthResponse:
    db_status = "ok"
    try:
        with get_db() as conn:
            conn.execute("SELECT 1;").fetchone()
    except Exception as exc:
        db_status = f"unhealthy: {str(exc)}"

    provider_statuses = await gateway.healthcheck_all()

    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        version=__version__,
        environment=settings.factory_env,
        database=db_status,
        providers=provider_statuses,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
