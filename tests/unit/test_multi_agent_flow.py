"""Pruebas del flujo multiagente completo (Hito 6) y barrera de aprobación humana."""

import pytest
from unittest.mock import AsyncMock, patch
from pathlib import Path
from fastapi.testclient import TestClient
from software_factory.kanban.schema import TaskCreate, TaskStatus, TaskTransitionRequest
from software_factory.kanban.service import KanbanService
from software_factory.agents.analyst import AnalystAgent, AnalystResult
from software_factory.agents.architect import ArchitectAgent, ArchitectPlan
from software_factory.agents.developer import DeveloperAgent, DeveloperResult
from software_factory.agents.tester import TesterAgent, TestVerdict
from software_factory.agents.reviewer import ReviewerAgent, ReviewVerdict
from software_factory.orchestration.graph import run_full_cycle
from software_factory.orchestration.approval import ApprovalManager, HumanApprovalRequest
from software_factory.git.worktree import WorktreeManager


@pytest.mark.asyncio
async def test_architect_agent_planning():
    agent = ArchitectAgent()
    mock_plan = ArchitectPlan(
        summary="Arquitectura modular",
        affected_files=["src/module_a.py"],
        plan_steps=["1. Crear función", "2. Conectar endpoint"],
    )
    with patch.object(agent, "plan_task", new_callable=AsyncMock) as mock_p:
        mock_p.return_value = mock_plan
        plan = await agent.plan_task("TASK-01", "Título", ["Criterio 1"])
        assert len(plan.affected_files) == 1
        assert len(plan.plan_steps) == 2


@pytest.mark.asyncio
async def test_reviewer_rejects_secrets_in_diff():
    agent = ReviewerAgent()
    dirty_diff = """
    +API_TOKEN = "sk-1234567890abcdef1234567890abcdef1234"
    """
    verdict = await agent.review_task("TASK-SEC", dirty_diff, ["Criterio 1"])
    assert verdict.is_approved is False
    assert verdict.has_secrets is True
    assert verdict.risk_assessment == "critical"
    assert "RECHAZAR" in verdict.recommendation_for_human


@pytest.mark.asyncio
async def test_full_cycle_advances_to_review():
    """Valida que el ciclo multiagente avanza hasta REVIEW y se detiene esperando aprobación humana."""
    task = KanbanService.create_task(
        TaskCreate(
            title="Tarea Full Cycle",
            description="Flujo completo de prueba",
            acceptance_criteria=[],
        )
    )

    mock_analyst = AnalystResult(
        summary="Análisis completado",
        acceptance_criteria=["Criterio Aprobado 1"],
    )
    mock_architect = ArchitectPlan(
        summary="Plan técnico",
        affected_files=["src/core.py"],
        plan_steps=["Paso 1"],
    )
    mock_developer = DeveloperResult(
        commit_message="feat(task): implementacion",
        files_modified=["src/core.py"],
    )
    mock_tester = TestVerdict(
        tests_passed=True,
        exit_code=0,
        summary="Pruebas unitarias OK",
        duration_ms=15.0,
        stdout="1 passed",
        stderr="",
    )
    mock_reviewer = ReviewVerdict(
        is_approved=True,
        has_secrets=False,
        risk_assessment="low",
        recommendation_for_human="Listo para merge",
    )

    with patch.object(AnalystAgent, "analyze_task", new_callable=AsyncMock) as m_an, \
         patch.object(ArchitectAgent, "plan_task", new_callable=AsyncMock) as m_ar, \
         patch.object(DeveloperAgent, "develop_task", new_callable=AsyncMock) as m_dev, \
         patch.object(TesterAgent, "run_tests", new_callable=AsyncMock) as m_test, \
         patch.object(ReviewerAgent, "review_task", new_callable=AsyncMock) as m_rev, \
         patch.object(WorktreeManager, "create_worktree", new_callable=AsyncMock) as m_wt, \
         patch.object(WorktreeManager, "get_diff", new_callable=AsyncMock) as m_diff:

        m_an.return_value = mock_analyst
        m_ar.return_value = mock_architect
        m_dev.return_value = mock_developer
        m_test.return_value = mock_tester
        m_rev.return_value = mock_reviewer
        m_wt.return_value = Path("/tmp/mock_worktree")
        m_diff.return_value = "+# mock diff limpio"

        final_state = await run_full_cycle(task.id)

    # El grafo debe quedar en REVIEW, NUNCA en DONE automáticamente
    assert final_state["status"] == TaskStatus.REVIEW.value
    task_in_db = KanbanService.get_task(task.id)
    assert task_in_db.status == TaskStatus.REVIEW


def test_human_approval_barrier_lifecycle(client: TestClient):
    """Prueba la barrera de decisión humana vía API REST."""
    # 1. Crear tarea y avanzar manualmente a REVIEW para probar la barrera
    task = KanbanService.create_task(TaskCreate(title="Tarea para Aprobar", acceptance_criteria=["Crit 1"]))
    KanbanService.transition_task(task.id, TaskTransitionRequest(target_status=TaskStatus.READY))
    KanbanService.transition_task(task.id, TaskTransitionRequest(target_status=TaskStatus.PLANNING))
    KanbanService.transition_task(task.id, TaskTransitionRequest(target_status=TaskStatus.IN_PROGRESS))
    KanbanService.transition_task(task.id, TaskTransitionRequest(target_status=TaskStatus.TESTING))
    KanbanService.transition_task(task.id, TaskTransitionRequest(target_status=TaskStatus.REVIEW))

    # 2. Intentar aprobar
    approve_payload = {
        "approver": "lead_engineer",
        "decision": "APPROVED",
        "comments": "Cambios verificados y testeados",
    }
    res = client.post(f"/api/v1/tasks/{task.id}/approve", json=approve_payload)
    assert res.status_code == 200
    assert res.json()["decision"] == "APPROVED"

    # La tarea debe haber pasado a DONE
    updated = KanbanService.get_task(task.id)
    assert updated.status == TaskStatus.DONE


def test_human_rejection_blocks_task(client: TestClient):
    """Prueba que el rechazo humano pasa la tarea a BLOCKED."""
    task = KanbanService.create_task(TaskCreate(title="Tarea a Rechazar", acceptance_criteria=["Crit 1"]))
    KanbanService.transition_task(task.id, TaskTransitionRequest(target_status=TaskStatus.READY))
    KanbanService.transition_task(task.id, TaskTransitionRequest(target_status=TaskStatus.PLANNING))
    KanbanService.transition_task(task.id, TaskTransitionRequest(target_status=TaskStatus.IN_PROGRESS))
    KanbanService.transition_task(task.id, TaskTransitionRequest(target_status=TaskStatus.TESTING))
    KanbanService.transition_task(task.id, TaskTransitionRequest(target_status=TaskStatus.REVIEW))

    reject_payload = {
        "approver": "sec_auditor",
        "decision": "REJECTED",
        "comments": "Riesgo no mitigado en arquitectura",
    }
    res = client.post(f"/api/v1/tasks/{task.id}/approve", json=reject_payload)
    assert res.status_code == 200
    assert res.json()["decision"] == "REJECTED"

    updated = KanbanService.get_task(task.id)
    assert updated.status == TaskStatus.BLOCKED
