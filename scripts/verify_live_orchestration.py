"""Prueba end-to-end en vivo del Agente Analista usando el servidor FCC real."""

import asyncio
from software_factory.kanban.schema import TaskCreate
from software_factory.kanban.service import KanbanService
from software_factory.orchestration.graph import run_analyst_flow
from software_factory.persistence.database import init_db


async def main():
    init_db()
    print("--- 1. Creando tarea en BACKLOG ---")
    task = KanbanService.create_task(
        TaskCreate(
            title="Implementar módulo de exportación de métricas a CSV",
            description="El sistema debe permitir descargar los tiempos de respuesta y consumo de tokens de las tareas completadas en formato CSV sanitizado.",
            priority="high",
            data_classification="approved_remote",
            acceptance_criteria=[],
        )
    )
    print(f"Tarea creada: ID={task.id} | Estado inicial={task.status.value}")

    print("\n--- 2. Ejecutando LangGraph con Agente Analista (usando fcc-server) ---")
    final_state = await run_analyst_flow(task.id)

    print(f"Estado final del grafo: {final_state['status']}")
    if final_state.get('error_message'):
        print(f"Mensaje de error: {final_state['error_message']}")
    print(f"Resumen del analista: {final_state.get('analyst_summary')}")
    print("\nCriterios de Aceptación generados:")
    for idx, crit in enumerate(final_state.get("acceptance_criteria", []), 1):
        print(f"  [{idx}] {crit}")

    print("\n--- 3. Verificando persistencia en SQLite ---")
    persisted_task = KanbanService.get_task(task.id)
    print(f"Tarea en DB: ID={persisted_task.id} | Estado={persisted_task.status.value}")
    print(f"Total criterios persistidos: {len(persisted_task.acceptance_criteria)}")


if __name__ == "__main__":
    asyncio.run(main())
