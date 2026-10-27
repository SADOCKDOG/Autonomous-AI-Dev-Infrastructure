"""Pruebas de integracion y gobernanza AI-GRC para el piloto Livestock Manager."""

import pytest
from software_factory.kanban.schema import TaskCreate, TaskStatus, TaskTransitionRequest
from software_factory.kanban.service import KanbanService
from software_factory.model_gateway.base import (
    ModelRequest,
    ChatMessage,
    PolicyViolationError,
)
from software_factory.model_gateway.fcc_provider import FCCAnthropicProvider
from software_factory.model_gateway.policy import ModelPolicyEngine
from software_factory.orchestration.approval import ApprovalManager, HumanApprovalRequest


def test_livestock_grc_prevents_unauthorized_pii_leak():
    """Verifica que datos ganaderos clasificados como restricted no salgan a modelos remotos."""
    provider = FCCAnthropicProvider(base_url="http://127.0.0.1:8082/v1", is_local_backend=False)
    request = ModelRequest(
        model="fcc-default",
        messages=[
            ChatMessage(
                role="user",
                content="Validar identificador REGA ES1100000001 y coordenadas GPS de explotacion.",
            )
        ],
        task_id="TASK-PILOT-01",
        data_classification="restricted",
        metadata={"human_approved": False},
    )

    with pytest.raises(PolicyViolationError) as exc_info:
        ModelPolicyEngine.validate_request(request, provider)

    assert "requiere aprobación humana" in str(exc_info.value)


def test_livestock_grc_allows_approved_remote_for_decoupled_logic():
    """Verifica que la logica de negocio desacoplada se admita bajo approved_remote."""
    provider = FCCAnthropicProvider(base_url="http://127.0.0.1:8082/v1", is_local_backend=False)
    request = ModelRequest(
        model="fcc-default",
        messages=[
            ChatMessage(
                role="user",
                content="Calcular periodo de supresion lactea segun RD 787/2023 con fecha y dias de espera.",
            )
        ],
        task_id="TASK-PILOT-02",
        data_classification="approved_remote",
        metadata={},
    )

    # No debe levantar excepcion de violacion de politica
    ModelPolicyEngine.validate_request(request, provider)


def test_livestock_task_human_approval_lifecycle():
    """Verifica que una tarea critica de Livestock Manager complete el ciclo de aprobacion auditada."""
    task = KanbanService.create_task(
        TaskCreate(
            title="SIGGAN: Calculo determinista de periodo de supresion farmacologica",
            description="Algoritmo de comprobacion de dias de retirada de medicamentos en leche.",
            priority="critical",
            data_classification="approved_remote",
            acceptance_criteria=["Debe bloquear albaran si dias restantes > 0"],
        )
    )

    # Simular transicion a REVIEW
    KanbanService.transition_task(
        task.id,
        TaskTransitionRequest(
            target_status=TaskStatus.REVIEW,
            agent_role="reviewer",
            reason="Revision de codigo y tests completada satisfactoriamente.",
        ),
    )

    # Registro de aprobacion humana formal
    decision = ApprovalManager.record_decision(
        task.id,
        HumanApprovalRequest(
            approver="director_tecnico_veterinario",
            decision="APPROVED",
            comments="Cumplimiento con RD 787/2023 validado.",
        ),
    )

    updated_task = KanbanService.get_task(task.id)
    assert decision.decision == "APPROVED"
    assert updated_task.status == TaskStatus.DONE

