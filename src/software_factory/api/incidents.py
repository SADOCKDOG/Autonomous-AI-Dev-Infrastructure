"""Rutas API para el gestor de incidencias operacionales y AI-GRC."""

from fastapi import APIRouter, HTTPException, Query, status
from software_factory.kanban.incidents import (
    IncidentService,
    Incident,
    IncidentCreate,
    IncidentResolve,
)

router = APIRouter(prefix="/api/v1/incidents", tags=["incidents"])


@router.post("", response_model=Incident, status_code=status.HTTP_201_CREATED)
def create_incident(payload: IncidentCreate) -> Incident:
    """Crea una nueva incidencia manual o del sistema."""
    return IncidentService.create_incident(payload)


@router.get("", response_model=list[Incident])
def list_incidents(
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
) -> list[Incident]:
    """Lista incidencias con filtrado por estado y severidad."""
    return IncidentService.list_incidents(status=status, severity=severity, limit=limit)


@router.get("/{incident_id}", response_model=Incident)
def get_incident(incident_id: str) -> Incident:
    """Obtiene los detalles de una incidencia."""
    try:
        return IncidentService.get_incident(incident_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.post("/{incident_id}/resolve", response_model=Incident)
def resolve_incident(incident_id: str, payload: IncidentResolve) -> Incident:
    """Registra la resolucion y cierre de una incidencia."""
    try:
        return IncidentService.resolve_incident(incident_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
