"""Pruebas del motor de orquestación con LangGraph y el Agente Analista."""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from software_factory.kanban.schema import TaskCreate, TaskStatus
from software_factory.kanban.service import KanbanService
from software_factory.agents.analyst import AnalystAgent, AnalystResult
from software_factory.orchestration.graph import run_analyst_flow
from software_factory.model_gateway.base import ModelResponse, ModelUsage


def test_analyst_parser_clean_json():
    agent = AnalystAgent()
    json_payload = """
    ```json
    {
      "summary": "Implementar autenticación JWT",
      "acceptance_criteria": [
        "El endpoint /login emite token con expiración 1h",
        "Rutas protegidas devuelven 401 si no hay token"
      ],
      "suggested_priority": "high",
      "functional_scope": ["auth", "security"]
    }
    ```
    """
    res = agent._parse_response(json_payload, "Default Title")
    assert res.summary == "Implementar autenticación JWT"
    assert len(res.acceptance_criteria) == 2
    assert res.suggested_priority == "high"


def test_analyst_parser_heuristic_fallback():
    agent = AnalystAgent()
    bullet_payload = """
    Aquí están los criterios necesarios:
    * 1. Probar que el endpoint /health responde 200
    * 2. Probar que la base de datos se inicializa en SQLite
    """
    res = agent._parse_response(bullet_payload, "Tarea de Salud")
    assert len(res.acceptance_criteria) == 2
    assert "200" in res.acceptance_criteria[0]


@pytest.mark.asyncio
async def test_langgraph_analyst_flow_success():
    """Valida el ciclo de vida completo en LangGraph: BACKLOG -> READY con criterios."""
    task = KanbanService.create_task(
        TaskCreate(
            title="Integración de Telemetría",
            description="Añadir métricas de latencia al gateway",
            acceptance_criteria=[],
        )
    )
    assert task.status == TaskStatus.BACKLOG

    mock_analyst_result = AnalystResult(
        summary="Métricas de latencia",
        acceptance_criteria=[
            "Cada llamada registra latency_ms en audit_logs",
            "El endpoint /health reporta latencia de cada proveedor",
        ],
        suggested_priority="medium",
        functional_scope=["telemetry"],
    )

    with patch.object(AnalystAgent, "analyze_task", new_callable=AsyncMock) as mock_analyze:
        mock_analyze.return_value = mock_analyst_result
        final_state = await run_analyst_flow(task.id)

    assert final_state["status"] == TaskStatus.READY.value
    assert len(final_state["acceptance_criteria"]) == 2

    # Verificar persistencia en base de datos
    updated_task = KanbanService.get_task(task.id)
    assert updated_task.status == TaskStatus.READY
    assert len(updated_task.acceptance_criteria) == 2


@pytest.mark.asyncio
async def test_langgraph_analyst_flow_error_blocks_task():
    """Valida contención de fallo: si el analista falla, el grafo transiciona a BLOCKED."""
    task = KanbanService.create_task(
        TaskCreate(
            title="Tarea con fallo simulado",
            acceptance_criteria=[],
        )
    )

    with patch.object(AnalystAgent, "analyze_task", new_callable=AsyncMock) as mock_analyze:
        mock_analyze.side_effect = RuntimeError("Error en conexión con proveedor")
        final_state = await run_analyst_flow(task.id)

    assert final_state["status"] == TaskStatus.BLOCKED.value
    updated_task = KanbanService.get_task(task.id)
    assert updated_task.status == TaskStatus.BLOCKED


def test_api_analyze_endpoint(client: TestClient):
    """Valida la invocación del orquestador a través de la API REST."""
    create_res = client.post(
        "/api/v1/tasks",
        json={"title": "Tarea vía REST API", "acceptance_criteria": []},
    )
    task_id = create_res.json()["id"]

    mock_result = AnalystResult(
        summary="Tarea procesada",
        acceptance_criteria=["Criterio API 1", "Criterio API 2"],
    )

    with patch.object(AnalystAgent, "analyze_task", new_callable=AsyncMock) as mock_analyze:
        mock_analyze.return_value = mock_result
        res = client.post(f"/api/v1/tasks/{task_id}/analyze")

    assert res.status_code == 200
    data = res.json()
    assert data["status"] == TaskStatus.READY.value
    assert len(data["acceptance_criteria"]) == 2
