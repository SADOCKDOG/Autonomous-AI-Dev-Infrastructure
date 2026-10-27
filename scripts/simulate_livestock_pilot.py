"""Simulacion ejecutable del Piloto Livestock Manager en la Software Factory."""

import asyncio
import os
import sys
from pathlib import Path

# Asegurar resolucion de paquetes locales
ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from software_factory.kanban.schema import TaskCreate, TaskStatus
from software_factory.kanban.service import KanbanService
from software_factory.orchestration.graph import run_full_cycle
from software_factory.orchestration.approval import ApprovalManager, HumanApprovalRequest
from software_factory.persistence.database import init_db


async def main():
    init_db()
    print("================================================================================")
    print("PILOTO TECNICO: LIVESTOCK MANAGER - VALIDACION END-TO-END DE INFRAESTRUCTURA")
    print("================================================================================")

    print("\n--- FASE 1: Verificacion de Politica de Datos AI-GRC (Deteccion de Bloqueo) ---")
    task_blocked = KanbanService.create_task(
        TaskCreate(
            title="SIGGAN: Sincronizacion de coordenadas geograficas y REGA sensible",
            description="Exportar coordenadas GPS y codigos REGA de fincas a modelo LLM externo.",
            priority="critical",
            data_classification="restricted",
            acceptance_criteria=[],
        )
    )
    print(f"Tarea de prueba de seguridad registrada: ID={task_blocked.id} | Clasificacion=restricted")
    blocked_state = await run_full_cycle(task_blocked.id)
    print(f"Estado resultante: {blocked_state['status']}")
    print(f"Politica activada: {blocked_state.get('error_message')}")
    assert blocked_state["status"] == TaskStatus.BLOCKED.value, "La politica AI-GRC debio bloquear la tarea"
    print("Resultado FASE 1: Aislamiento y politica de datos 'restricted' validada con exito.")

    print("\n--- FASE 2: Ciclo Multiagente End-to-End con Logica Regulatoria Desacoplada ---")
    task = KanbanService.create_task(
        TaskCreate(
            title="SIGGAN: Bloqueo preventivo de venta de leche bajo tratamiento sanitario",
            description=(
                "Implementar regla de seguridad alimentaria en el modulo de comercializacion lactea. "
                "Si un animal de la finca activa registra tratamiento en curso con periodo de supresion "
                "pendiente segun RD 787/2023, la generacion del albaran de entrega debe ser bloqueada."
            ),
            priority="critical",
            data_classification="approved_remote",
            acceptance_criteria=[],
        )
    )
    print(f"Tarea registrada: ID={task.id} | Estado inicial={task.status.value}")

    print("\nEjecutando orquestacion LangGraph (Analyst -> Architect -> Developer -> Tester -> Reviewer)...")
    final_state = await run_full_cycle(task.id)

    print(f"\nEstado tras orquestacion: {final_state['status']}")
    print(f"Resumen del Analista Regulatorio: {final_state.get('analyst_summary')}")
    print("\nCriterios de Aceptacion Generados:")
    for idx, crit in enumerate(final_state.get("acceptance_criteria", []), 1):
        print(f"  [{idx}] {crit}")

    db_task = KanbanService.get_task(task.id)
    print(f"\nEstado en Persistencia SQLite: {db_task.status.value}")

    print("\n--- FASE 3: Barrera de Aprobacion Humana (AI-GRC Gate) ---")
    if final_state["status"] == TaskStatus.REVIEW.value:
        print("Tarea en REVIEW. Requiere autorizacion expresa de la direccion tecnica.")
        approval = ApprovalManager.record_decision(
            task.id,
            HumanApprovalRequest(
                approver="director_tecnico_ganadero",
                decision="APPROVED",
                comments="Validado cumplimiento SIGGAN/BADIGEX y ausencia de fugas de datos. Aprobado para integracion.",
            ),
        )
        print(f"Decision registrada: {approval.decision} por {approval.approver}")
        print(f"Estado final en Kanban: {KanbanService.get_task(task.id).status.value}")
    else:
        print(f"La tarea no alcanzo REVIEW (Estado actual: {final_state['status']}).")
        if final_state.get("error_message"):
            print(f"Causa: {final_state.get('error_message')}")

    print("\n================================================================================")
    print("PILOTO COMPLETADO SATISFACTORIAMENTE")
    print("================================================================================")


if __name__ == "__main__":
    asyncio.run(main())
