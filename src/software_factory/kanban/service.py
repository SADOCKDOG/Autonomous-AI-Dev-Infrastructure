"""Servicio de lógica y transiciones de tareas Kanban."""

import json
import uuid
from typing import Any
from software_factory.persistence.database import get_db
from software_factory.kanban.schema import (
    TaskCreate,
    TaskResponse,
    TaskStatus,
    TaskTransitionRequest,
    TaskPriority,
    DataClassification,
)


class KanbanValidationError(ValueError):
    """Excepción para transiciones no válidas según la especificación."""
    pass


class KanbanService:
    @staticmethod
    def create_task(task_in: TaskCreate) -> TaskResponse:
        task_id = f"TASK-{uuid.uuid4().hex[:8].upper()}"
        initial_status = TaskStatus.BACKLOG

        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO tasks (
                    id, title, description, status, priority, data_classification,
                    acceptance_criteria, target_repo
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    task_in.title,
                    task_in.description,
                    initial_status.value,
                    task_in.priority.value,
                    task_in.data_classification.value,
                    json.dumps(task_in.acceptance_criteria),
                    task_in.target_repo,
                ),
            )
            # Registrar evento inicial
            conn.execute(
                """
                INSERT INTO task_events (task_id, event_type, from_status, to_status, agent_role, payload)
                VALUES (?, 'CREATED', NULL, ?, 'coordinator', ?)
                """,
                (task_id, initial_status.value, json.dumps({"title": task_in.title})),
            )

        return KanbanService.get_task(task_id)

    @staticmethod
    def get_task(task_id: str) -> TaskResponse:
        with get_db() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if not row:
                raise KeyError(f"Tarea {task_id} no encontrada")

            return TaskResponse(
                id=row["id"],
                title=row["title"],
                description=row["description"],
                status=TaskStatus(row["status"]),
                priority=TaskPriority(row["priority"]),
                data_classification=DataClassification(row["data_classification"]),
                acceptance_criteria=json.loads(row["acceptance_criteria"]),
                assigned_agent=row["assigned_agent"],
                branch_name=row["branch_name"],
                worktree_path=row["worktree_path"],
                target_repo=row["target_repo"] if "target_repo" in row.keys() else None,
                created_at=str(row["created_at"]),
                updated_at=str(row["updated_at"]),
            )

    @staticmethod
    def list_tasks(status: TaskStatus | None = None) -> list[TaskResponse]:
        with get_db() as conn:
            query = "SELECT * FROM tasks"
            params: tuple[Any, ...] = ()
            if status:
                query += " WHERE status = ?"
                params = (status.value,)
            query += " ORDER BY created_at DESC"
            
            rows = conn.execute(query, params).fetchall()
            return [
                TaskResponse(
                    id=r["id"],
                    title=r["title"],
                    description=r["description"],
                    status=TaskStatus(r["status"]),
                    priority=TaskPriority(r["priority"]),
                    data_classification=DataClassification(r["data_classification"]),
                    acceptance_criteria=json.loads(r["acceptance_criteria"]),
                    assigned_agent=r["assigned_agent"],
                    branch_name=r["branch_name"],
                    worktree_path=r["worktree_path"],
                    target_repo=r["target_repo"] if "target_repo" in r.keys() else None,
                    created_at=str(r["created_at"]),
                    updated_at=str(r["updated_at"]),
                )
                for r in rows
            ]

    @staticmethod
    def transition_task(task_id: str, request: TaskTransitionRequest) -> TaskResponse:
        task = KanbanService.get_task(task_id)
        current_status = task.status
        target_status = request.target_status

        # Validaciones de reglas de negocio
        if target_status == TaskStatus.READY:
            if not task.acceptance_criteria:
                raise KanbanValidationError(
                    "Para pasar a READY se requiere al menos un criterio de aceptación definido."
                )

        if target_status == TaskStatus.IN_PROGRESS:
            # Debe existir o asignarse rama para aislar el cambio
            branch = task.branch_name or f"feat/{task_id.lower()}"
        else:
            branch = task.branch_name

        with get_db() as conn:
            conn.execute(
                """
                UPDATE tasks 
                SET status = ?, branch_name = ?, assigned_agent = COALESCE(?, assigned_agent), updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (target_status.value, branch, request.agent_role, task_id),
            )
            # Evento y Auditoría
            conn.execute(
                """
                INSERT INTO task_events (task_id, event_type, from_status, to_status, agent_role, payload)
                VALUES (?, 'STATUS_CHANGE', ?, ?, ?, ?)
                """,
                (
                    task_id,
                    current_status.value,
                    target_status.value,
                    request.agent_role or "system",
                    json.dumps({"reason": request.reason, **request.metadata}),
                ),
            )
            conn.execute(
                """
                INSERT INTO audit_logs (task_id, action, actor, details)
                VALUES (?, 'TRANSITION', ?, ?)
                """,
                (
                    task_id,
                    request.agent_role or "system",
                    json.dumps({
                        "from": current_status.value,
                        "to": target_status.value,
                        "reason": request.reason
                    }),
                ),
            )

        return KanbanService.get_task(task_id)
