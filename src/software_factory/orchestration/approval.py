"""Gestor de la barrera de aprobación humana obligatoria."""

import json
from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel
from software_factory.persistence.database import get_db
from software_factory.kanban.service import KanbanService
from software_factory.kanban.schema import TaskStatus, TaskTransitionRequest


class HumanApprovalRequest(BaseModel):
    approver: str
    decision: Literal["APPROVED", "REJECTED"]
    comments: str = ""


class HumanApprovalRecord(BaseModel):
    task_id: str
    approver: str
    decision: str
    comments: str
    created_at: str


class ApprovalManager:
    """Gestiona las aprobaciones humanas antes de merge, push o cierre a DONE."""

    @classmethod
    def record_decision(cls, task_id: str, request: HumanApprovalRequest) -> HumanApprovalRecord:
        record = HumanApprovalRecord(
            task_id=task_id,
            approver=request.approver,
            decision=request.decision,
            comments=request.comments,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO audit_logs (task_id, action, actor, details)
                VALUES (?, 'HUMAN_APPROVAL', ?, ?)
                """,
                (task_id, request.approver, record.model_dump_json()),
            )

        # Si es rechazado, pasar a BLOCKED
        if request.decision == "REJECTED":
            KanbanService.transition_task(
                task_id,
                TaskTransitionRequest(
                    target_status=TaskStatus.BLOCKED,
                    agent_role="human_approver",
                    reason=f"Rechazado por aprobador humano ({request.approver}): {request.comments}",
                ),
            )
        elif request.decision == "APPROVED":
            # Si es aprobado, puede transicionar a DONE
            KanbanService.transition_task(
                task_id,
                TaskTransitionRequest(
                    target_status=TaskStatus.DONE,
                    agent_role="human_approver",
                    reason=f"Aprobado por {request.approver}: {request.comments}",
                ),
            )

        return record

    @classmethod
    def has_approval(cls, task_id: str) -> bool:
        with get_db() as conn:
            row = conn.execute(
                """
                SELECT details FROM audit_logs 
                WHERE task_id = ? AND action = 'HUMAN_APPROVAL'
                ORDER BY created_at DESC LIMIT 1
                """,
                (task_id,),
            ).fetchone()

            if not row:
                return False
            data = json.loads(row["details"])
            return data.get("decision") == "APPROVED"
