"""Pruebas de persistencia y lógica de negocio del Kanban."""

import pytest
from fastapi.testclient import TestClient
from software_factory.kanban.schema import TaskStatus


def test_create_task_and_persistence(client: TestClient):
    payload = {
        "title": "Configurar Model Gateway",
        "description": "Implementar adaptadores de inferencia",
        "priority": "high",
        "data_classification": "approved_remote",
        "acceptance_criteria": ["Adaptador FCC funciona", "Mocks pasan"]
    }
    response = client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 201
    task = response.json()
    assert task["id"].startswith("TASK-")
    assert task["status"] == TaskStatus.BACKLOG.value
    assert len(task["acceptance_criteria"]) == 2

    # Verificar lectura persistida
    get_res = client.get(f"/api/v1/tasks/{task['id']}")
    assert get_res.status_code == 200
    assert get_res.json()["title"] == payload["title"]


def test_transition_to_ready_requires_acceptance_criteria(client: TestClient):
    # Crear tarea sin criterios
    payload = {
        "title": "Tarea sin criterios",
        "description": "Prueba de validación",
        "acceptance_criteria": []
    }
    res = client.post("/api/v1/tasks", json=payload)
    task_id = res.json()["id"]

    # Intentar pasar a READY debe fallar con 422
    trans_res = client.post(
        f"/api/v1/tasks/{task_id}/transition",
        json={"target_status": TaskStatus.READY.value, "reason": "Intento prematuro"}
    )
    assert trans_res.status_code == 422
    assert "al menos un criterio de aceptación" in trans_res.json()["detail"]


def test_transition_lifecycle(client: TestClient):
    payload = {
        "title": "Flujo de trabajo completo",
        "acceptance_criteria": ["Criterio 1 cumplido"]
    }
    res = client.post("/api/v1/tasks", json=payload)
    task_id = res.json()["id"]

    # 1. Pasar a READY
    res_ready = client.post(
        f"/api/v1/tasks/{task_id}/transition",
        json={"target_status": TaskStatus.READY.value, "agent_role": "analyst"}
    )
    assert res_ready.status_code == 200
    assert res_ready.json()["status"] == TaskStatus.READY.value

    # 2. Pasar a PLANNING
    res_plan = client.post(
        f"/api/v1/tasks/{task_id}/transition",
        json={"target_status": TaskStatus.PLANNING.value, "agent_role": "architect"}
    )
    assert res_plan.status_code == 200
    assert res_plan.json()["status"] == TaskStatus.PLANNING.value

    # 3. Pasar a IN_PROGRESS (debe asignar rama por defecto)
    res_prog = client.post(
        f"/api/v1/tasks/{task_id}/transition",
        json={"target_status": TaskStatus.IN_PROGRESS.value, "agent_role": "developer"}
    )
    assert res_prog.status_code == 200
    data = res_prog.json()
    assert data["status"] == TaskStatus.IN_PROGRESS.value
    assert data["branch_name"] == f"feat/{task_id.lower()}"
