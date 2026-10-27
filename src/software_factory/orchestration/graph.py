"""Definición y compilación del grafo de estados con LangGraph."""

import json
from langgraph.graph import StateGraph, START, END
from software_factory.orchestration.state import FactoryState
from software_factory.agents.analyst import AnalystAgent
from software_factory.kanban.service import KanbanService
from software_factory.kanban.schema import TaskStatus, TaskTransitionRequest
from software_factory.persistence.database import get_db


async def analyst_node(state: FactoryState) -> FactoryState:
    """Nodo del Analista: descompone la tarea y formula criterios de aceptación."""
    task_id = state["task_id"]
    title = state.get("title", "")
    description = state.get("description", "")
    classification = state.get("data_classification", "project_context")
    
    agent = AnalystAgent()
    try:
        result = await agent.analyze_task(
            task_id=task_id,
            title=title,
            description=description,
            data_classification=classification,
        )

        criteria = result.acceptance_criteria
        if not criteria:
            return {
                **state,
                "error_message": "El analista no pudo generar criterios de aceptación válidos.",
            }

        # Actualizar en la base de datos local SQLite los criterios de aceptación
        with get_db() as conn:
            conn.execute(
                "UPDATE tasks SET acceptance_criteria = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (json.dumps(criteria), task_id),
            )

        # Transicionar tarea a READY
        KanbanService.transition_task(
            task_id,
            TaskTransitionRequest(
                target_status=TaskStatus.READY,
                agent_role="analyst",
                reason="Criterios de aceptación formulados con éxito por el Agente Analista.",
                metadata={"criteria_count": len(criteria), "summary": result.summary},
            ),
        )

        return {
            **state,
            "status": TaskStatus.READY.value,
            "acceptance_criteria": criteria,
            "analyst_summary": result.summary,
            "suggested_priority": result.suggested_priority,
            "functional_scope": result.functional_scope,
            "error_message": None,
        }
    except Exception as exc:
        return {
            **state,
            "error_message": f"Fallo en nodo analista: {str(exc)}",
        }


async def error_node(state: FactoryState) -> FactoryState:
    """Nodo de contención: bloquea la tarea con razón visible en auditoría si ocurre un fallo."""
    task_id = state["task_id"]
    error_msg = state.get("error_message") or "Error no especificado durante la orquestación."

    KanbanService.transition_task(
        task_id,
        TaskTransitionRequest(
            target_status=TaskStatus.BLOCKED,
            agent_role="coordinator",
            reason=error_msg,
        ),
    )
    return {
        **state,
        "status": TaskStatus.BLOCKED.value,
    }


def should_continue_after_analyst(state: FactoryState) -> str:
    """Ruta condicional: si hay error va a error_node, si fue exitoso finaliza en READY."""
    if state.get("error_message"):
        return "error_node"
    return END


def build_factory_graph():
    """Construye y compila el StateGraph de LangGraph."""
    graph = StateGraph(FactoryState)

    graph.add_node("analyst_node", analyst_node)
    graph.add_node("error_node", error_node)

    graph.add_edge(START, "analyst_node")
    graph.add_conditional_edges("analyst_node", should_continue_after_analyst)
    graph.add_edge("error_node", END)

    return graph.compile()


factory_graph = build_factory_graph()


async def run_analyst_flow(task_id: str) -> FactoryState:
    """Ejecuta el flujo del analista para una tarea existente en el Kanban."""
    task = KanbanService.get_task(task_id)
    initial_state: FactoryState = {
        "task_id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status.value,
        "data_classification": task.data_classification.value,
        "acceptance_criteria": task.acceptance_criteria,
        "iteration_count": 0,
        "max_iterations": 3,
        "error_message": None,
    }

    final_state = await factory_graph.ainvoke(initial_state)
    return final_state
