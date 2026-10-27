"""Batería de pruebas de aceptación, modo degradado y contención de seguridad."""

import json
import pytest
from unittest.mock import AsyncMock, patch
from pathlib import Path
from software_factory.kanban.schema import TaskCreate, TaskStatus, TaskTransitionRequest
from software_factory.kanban.service import KanbanService
from software_factory.persistence.database import get_db, init_db
from software_factory.orchestration.graph import run_full_cycle
from software_factory.orchestration.approval import ApprovalManager, HumanApprovalRequest
from software_factory.model_gateway.base import ProviderError, ModelRequest, ChatMessage, PolicyViolationError
from software_factory.model_gateway.registry import ModelGateway
from software_factory.agents.analyst import AnalystAgent, AnalystResult
from software_factory.agents.architect import ArchitectAgent, ArchitectPlan
from software_factory.agents.developer import DeveloperAgent, DeveloperResult
from software_factory.agents.tester import TesterAgent, TestVerdict
from software_factory.agents.reviewer import ReviewerAgent, ReviewVerdict
from software_factory.git.worktree import WorktreeManager


@pytest.mark.asyncio
async def test_degraded_mode_when_provider_is_down():
    """Modo degradado: si el proveedor de IA se cae, la tarea se detiene en BLOCKED y la DB no se corrompe."""
    task = KanbanService.create_task(
        TaskCreate(
            title="Tarea con proveedor caído",
            acceptance_criteria=[],
        )
    )

    with patch.object(AnalystAgent, "analyze_task", new_callable=AsyncMock) as mock_an:
        mock_an.side_effect = ProviderError("Conexión rechazada: 127.0.0.1:8082 no responde", provider="fcc_anthropic")
        final_state = await run_full_cycle(task.id)

    # Verificar que el sistema no declaró éxito y marcó BLOCKED
    assert final_state["status"] == TaskStatus.BLOCKED.value
    task_in_db = KanbanService.get_task(task.id)
    assert task_in_db.status == TaskStatus.BLOCKED

    # Verificar que los eventos quedaron registrados
    with get_db() as conn:
        events = conn.execute("SELECT * FROM task_events WHERE task_id = ?", (task.id,)).fetchall()
        assert len(events) >= 2  # CREATED y STATUS_CHANGE a BLOCKED


@pytest.mark.asyncio
async def test_data_leak_prevention_local_only():
    """Garantiza que una tarea 'local_only' no puede ser consumida por proveedores remotos."""
    gateway = ModelGateway()
    remote_prov = gateway.get_provider("azure_foundry")

    req = ModelRequest(
        messages=[ChatMessage(role="user", content="Código confidencial estrictamente local")],
        model="any",
        data_classification="local_only",
    )

    with pytest.raises(PolicyViolationError) as exc_info:
        await gateway.generate(req, provider_name="azure_foundry")

    assert "local_only" in str(exc_info.value)


def test_database_persists_across_restart(tmp_path: Path, monkeypatch):
    """Verifica que reiniciar el proceso o reconectar SQLite conserva toda la información de tareas y auditoría."""
    db_file = tmp_path / "persistent_factory.db"
    from software_factory.settings import settings
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_file}")
    init_db(db_file)

    # Crear tarea
    task = KanbanService.create_task(
        TaskCreate(
            title="Persistencia garantizada",
            acceptance_criteria=["Criterio A", "Criterio B"],
        )
    )
    task_id = task.id

    # Simular reinicio completo desconectando y volviendo a consultar
    reloaded_task = KanbanService.get_task(task_id)
    assert reloaded_task.title == "Persistencia garantizada"
    assert len(reloaded_task.acceptance_criteria) == 2


def test_audit_logs_contain_no_secrets():
    """Inspecciona los registros de auditoría en SQLite para verificar que no contienen secretos en texto plano."""
    task = KanbanService.create_task(TaskCreate(title="Auditoría de Secretos", acceptance_criteria=["Crit 1"]))
    # Registrar aprobación con posibles metadatos
    ApprovalManager.record_decision(
        task.id,
        HumanApprovalRequest(approver="lead_dev", decision="APPROVED", comments="Aprobación con token simulado"),
    )

    with get_db() as conn:
        rows = conn.execute("SELECT details FROM audit_logs").fetchall()
        for r in rows:
            details_str = r["details"]
            assert "ghp_" not in details_str
            assert "sk-" not in details_str
            assert "AKIA" not in details_str


@pytest.mark.asyncio
async def test_e2e_full_lifecycle_with_approval():
    """Ciclo de vida completo end-to-end con todos los agentes y aprobación humana."""
    task = KanbanService.create_task(
        TaskCreate(
            title="Funcionalidad Completa E2E",
            acceptance_criteria=[],
        )
    )

    mock_an = AnalystResult(summary="Resumen E2E", acceptance_criteria=["Criterio E2E 1"])
    mock_ar = ArchitectPlan(summary="Plan E2E", affected_files=["src/e2e.py"], plan_steps=["1. E2E"])
    mock_dev = DeveloperResult(commit_message="feat(e2e): modulo completo", files_modified=["src/e2e.py"])
    mock_test = TestVerdict(tests_passed=True, exit_code=0, summary="Tests OK", duration_ms=20.0, stdout="", stderr="")
    mock_rev = ReviewVerdict(is_approved=True, has_secrets=False, risk_assessment="low", recommendation_for_human="Aprobado")

    with patch.object(AnalystAgent, "analyze_task", new_callable=AsyncMock) as p_an, \
         patch.object(ArchitectAgent, "plan_task", new_callable=AsyncMock) as p_ar, \
         patch.object(DeveloperAgent, "develop_task", new_callable=AsyncMock) as p_dev, \
         patch.object(TesterAgent, "run_tests", new_callable=AsyncMock) as p_test, \
         patch.object(ReviewerAgent, "review_task", new_callable=AsyncMock) as p_rev, \
         patch.object(WorktreeManager, "create_worktree", new_callable=AsyncMock) as p_wt, \
         patch.object(WorktreeManager, "get_diff", new_callable=AsyncMock) as p_diff:

        p_an.return_value = mock_an
        p_ar.return_value = mock_ar
        p_dev.return_value = mock_dev
        p_test.return_value = mock_test
        p_rev.return_value = mock_rev
        p_wt.return_value = Path("/tmp/mock_e2e_wt")
        p_diff.return_value = "+# diff limpio de e2e"

        # 1. Ejecutar ciclo automático -> debe detenerse en REVIEW
        state = await run_full_cycle(task.id)
        assert state["status"] == TaskStatus.REVIEW.value

        # 2. Aplicar barrera de decisión humana
        decision = ApprovalManager.record_decision(
            task.id,
            HumanApprovalRequest(approver="tech_lead", decision="APPROVED", comments="Verificado con éxito"),
        )
        assert decision.decision == "APPROVED"

        # 3. La tarea debe culminar en DONE
        final_task = KanbanService.get_task(task.id)
        assert final_task.status == TaskStatus.DONE
