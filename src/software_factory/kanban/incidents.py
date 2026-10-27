"""Servicio de gestion de incidencias operacionales y AI-GRC."""

import json
import uuid
from typing import Any
from pydantic import BaseModel, Field
from software_factory.persistence.database import get_db


class IncidentCreate(BaseModel):
    task_id: str | None = None
    title: str
    description: str = ""
    severity: str = "medium"  # low, medium, high, critical
    category: str = "policy_violation"  # policy_violation, secret_detected, sandbox_failure, timeout, manual
    reported_by: str = "system"


class IncidentResolve(BaseModel):
    resolution_notes: str
    resolved_by: str = "operador_humano"
    status: str = "resolved"  # resolved, closed


class Incident(BaseModel):
    id: str
    task_id: str | None
    title: str
    description: str
    severity: str
    category: str
    status: str
    reported_by: str
    resolution_notes: str = ""
    resolved_by: str | None = None
    created_at: str
    updated_at: str


class IncidentService:
    """Gestiona el ciclo de vida de incidencias en SQLite."""

    @staticmethod
    def create_incident(data: IncidentCreate) -> Incident:
        incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
        with get_db() as conn:
            conn.execute(
                """
                INSERT INTO incidents (
                    id, task_id, title, description, severity, category, status, reported_by
                ) VALUES (?, ?, ?, ?, ?, ?, 'open', ?)
                """,
                (
                    incident_id,
                    data.task_id,
                    data.title,
                    data.description,
                    data.severity,
                    data.category,
                    data.reported_by,
                ),
            )
            # Registrar en audit_logs
            conn.execute(
                """
                INSERT INTO audit_logs (task_id, action, actor, details)
                VALUES (?, 'INCIDENT_CREATED', ?, ?)
                """,
                (
                    data.task_id,
                    data.reported_by,
                    json.dumps({
                        "incident_id": incident_id,
                        "title": data.title,
                        "severity": data.severity,
                        "category": data.category,
                    }),
                ),
            )
        return IncidentService.get_incident(incident_id)

    @staticmethod
    def get_incident(incident_id: str) -> Incident:
        with get_db() as conn:
            cursor = conn.execute(
                "SELECT id, task_id, title, description, severity, category, status, reported_by, "
                "resolution_notes, resolved_by, created_at, updated_at FROM incidents WHERE id = ?",
                (incident_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError(f"Incidencia no encontrada: {incident_id}")
            return Incident(
                id=row[0],
                task_id=row[1],
                title=row[2],
                description=row[3],
                severity=row[4],
                category=row[5],
                status=row[6],
                reported_by=row[7],
                resolution_notes=row[8] or "",
                resolved_by=row[9],
                created_at=str(row[10]),
                updated_at=str(row[11]),
            )

    @staticmethod
    def list_incidents(
        status: str | None = None,
        severity: str | None = None,
        limit: int = 100,
    ) -> list[Incident]:
        query = (
            "SELECT id, task_id, title, description, severity, category, status, reported_by, "
            "resolution_notes, resolved_by, created_at, updated_at FROM incidents WHERE 1=1"
        )
        params: list[Any] = []
        if status and status != "all":
            query += " AND status = ?"
            params.append(status)
        if severity and severity != "all":
            query += " AND severity = ?"
            params.append(severity)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with get_db() as conn:
            cursor = conn.execute(query, tuple(params))
            return [
                Incident(
                    id=row[0],
                    task_id=row[1],
                    title=row[2],
                    description=row[3],
                    severity=row[4],
                    category=row[5],
                    status=row[6],
                    reported_by=row[7],
                    resolution_notes=row[8] or "",
                    resolved_by=row[9],
                    created_at=str(row[10]),
                    updated_at=str(row[11]),
                )
                for row in cursor.fetchall()
            ]

    @staticmethod
    def resolve_incident(incident_id: str, data: IncidentResolve) -> Incident:
        with get_db() as conn:
            conn.execute(
                """
                UPDATE incidents
                SET status = ?, resolution_notes = ?, resolved_by = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (data.status, data.resolution_notes, data.resolved_by, incident_id),
            )
            # Registrar en audit_logs
            conn.execute(
                """
                INSERT INTO audit_logs (action, actor, details)
                VALUES ('INCIDENT_RESOLVED', ?, ?)
                """,
                (
                    data.resolved_by,
                    json.dumps({
                        "incident_id": incident_id,
                        "status": data.status,
                        "notes": data.resolution_notes,
                    }),
                ),
            )
        return IncidentService.get_incident(incident_id)
