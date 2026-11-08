"""Rutas REST para el tablero Kanban, orquestación y aprobación humana."""

from fastapi import APIRouter, HTTPException, Query
from software_factory.kanban.schema import (
    TaskCreate,
    TaskResponse,
    TaskStatus,
    TaskTransitionRequest,
)
from software_factory.kanban.service import KanbanService, KanbanValidationError
from software_factory.orchestration.graph import run_analyst_flow, run_full_cycle

router = APIRouter(prefix="/api/v1/tasks", tags=["Kanban"])


@router.post("", response_model=TaskResponse, status_code=201)
def create_task(task_in: TaskCreate) -> TaskResponse:
    try:
        return KanbanService.create_task(task_in)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("", response_model=list[TaskResponse])
def list_tasks(status: TaskStatus | None = Query(default=None)) -> list[TaskResponse]:
    return KanbanService.list_tasks(status)


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: str) -> TaskResponse:
    try:
        return KanbanService.get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{task_id}/transition", response_model=TaskResponse)
def transition_task(task_id: str, request: TaskTransitionRequest) -> TaskResponse:
    try:
        return KanbanService.transition_task(task_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except KanbanValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/{task_id}/analyze", response_model=TaskResponse)
async def analyze_task(task_id: str) -> TaskResponse:
    """Ejecuta solo la fase de análisis inicial para clarificar criterios."""
    try:
        KanbanService.get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    state = await run_analyst_flow(task_id)
    if state.get("error_message"):
        raise HTTPException(status_code=500, detail=state["error_message"])

    return KanbanService.get_task(task_id)


@router.post("/{task_id}/run_full_cycle", response_model=TaskResponse)
async def execute_full_cycle(task_id: str) -> TaskResponse:
    """Ejecuta el ciclo multiagente completo (Analista -> Arquitecto -> Desarrollador -> QA -> Revisor)."""
    try:
        KanbanService.get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

    state = await run_full_cycle(task_id)
    return KanbanService.get_task(task_id)


@router.post("/{task_id}/approve")
def human_approve_task(task_id: str) -> dict:
    """Deprecated unsigned route; caller-supplied approver is not an identity proof."""
    raise HTTPException(
        status_code=410,
        detail="Unsigned task approval is disabled; use the signed PR/SHA owner-authorization flow.",
    )
