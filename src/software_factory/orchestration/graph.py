"""Grafo completo de orquestación multiagente con LangGraph."""

import json
from pathlib import Path
from langgraph.graph import StateGraph, START, END
from software_factory.orchestration.state import FactoryState
from software_factory.agents.analyst import AnalystAgent
from software_factory.agents.architect import ArchitectAgent
from software_factory.agents.developer import DeveloperAgent
from software_factory.agents.tester import TesterAgent
from software_factory.agents.reviewer import ReviewerAgent
from software_factory.agents.uiux import UIUXAgent
from software_factory.git.worktree import WorktreeManager
from software_factory.kanban.service import KanbanService
from software_factory.kanban.schema import TaskStatus, TaskTransitionRequest
from software_factory.persistence.database import get_db
from software_factory.profiler.loader import load_profile_from_repo, check_protected_paths


# --- 1. Nodos de Agentes ---

async def analyst_node(state: FactoryState) -> FactoryState:
    task_id = state["task_id"]
    agent = AnalystAgent()
    try:
        result = await agent.analyze_task(
            task_id=task_id,
            title=state.get("title", ""),
            description=state.get("description", ""),
            data_classification=state.get("data_classification", "project_context"),
        )
        if not result.acceptance_criteria:
            return {**state, "error_message": "El analista no generó criterios válidos."}

        with get_db() as conn:
            conn.execute(
                "UPDATE tasks SET acceptance_criteria = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (json.dumps(result.acceptance_criteria), task_id),
            )

        KanbanService.transition_task(
            task_id,
            TaskTransitionRequest(
                target_status=TaskStatus.READY,
                agent_role="analyst",
                reason="Criterios de aceptación definidos.",
            ),
        )
        return {
            **state,
            "status": TaskStatus.READY.value,
            "acceptance_criteria": result.acceptance_criteria,
            "analyst_summary": result.summary,
            "error_message": None,
        }
    except Exception as exc:
        return {**state, "error_message": f"Fallo en analista: {str(exc)}"}


async def architect_node(state: FactoryState) -> FactoryState:
    task_id = state["task_id"]
    agent = ArchitectAgent()
    try:
        plan = await agent.plan_task(
            task_id=task_id,
            title=state.get("title", ""),
            acceptance_criteria=state.get("acceptance_criteria", []),
            data_classification=state.get("data_classification", "project_context"),
        )
        KanbanService.transition_task(
            task_id,
            TaskTransitionRequest(
                target_status=TaskStatus.PLANNING,
                agent_role="architect",
                reason="Plan arquitectónico técnico elaborado.",
                metadata={"affected_files": plan.affected_files},
            ),
        )
        return {
            **state,
            "status": TaskStatus.PLANNING.value,
            "architect_plan": plan.model_dump(),
            "error_message": None,
        }
    except Exception as exc:
        return {**state, "error_message": f"Fallo en arquitecto: {str(exc)}"}


async def developer_node(state: FactoryState) -> FactoryState:
    task_id = state["task_id"]
    wt_manager = WorktreeManager()
    agent = DeveloperAgent()
    try:
        worktree_path = await wt_manager.create_worktree(task_id)

        # Actualizar ruta de worktree en la BD
        with get_db() as conn:
            conn.execute(
                "UPDATE tasks SET worktree_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (str(worktree_path), task_id),
            )

        KanbanService.transition_task(
            task_id,
            TaskTransitionRequest(
                target_status=TaskStatus.IN_PROGRESS,
                agent_role="developer",
                reason=f"Worktree aislado creado en {worktree_path}.",
            ),
        )

        plan_data = state.get("architect_plan") or {}
        dev_res = await agent.develop_task(
            task_id=task_id,
            title=state.get("title", ""),
            plan_summary=plan_data.get("summary", ""),
            plan_steps=plan_data.get("plan_steps", []),
            worktree_path=worktree_path,
            data_classification=state.get("data_classification", "approved_code_context"),
        )

        return {
            **state,
            "status": TaskStatus.IN_PROGRESS.value,
            "developer_result": dev_res.model_dump(),
            "error_message": None,
        }
    except Exception as exc:
        return {**state, "error_message": f"Fallo en desarrollador: {str(exc)}"}


async def uiux_node(state: FactoryState) -> FactoryState:
    """Nodo auditor de ergonomía y conformidad de tokens de interfaz (Modo Asesor)."""
    task_id = state["task_id"]
    wt_manager = WorktreeManager()
    agent = UIUXAgent()
    try:
        worktree_path = wt_manager.get_worktree_path(task_id)
        profile = load_profile_from_repo(worktree_path)
        changed_files = await wt_manager.get_changed_files(task_id, base_branch=profile.base_branch)
        diff_text = await wt_manager.get_diff(task_id, base_branch=profile.base_branch)

        verdict = await agent.evaluate_ui(
            task_id=task_id,
            worktree_path=worktree_path,
            profile=profile,
            changed_files=changed_files,
            diff_text=diff_text,
        )

        if not verdict.passed:
            return {
                **state,
                "uiux_verdict": verdict.model_dump(),
                "error_message": f"Evaluación UI/UX falló en modo estricto: {verdict.summary}",
            }

        return {
            **state,
            "uiux_verdict": verdict.model_dump(),
            "error_message": None,
        }
    except Exception as exc:
        return {**state, "error_message": f"Fallo en evaluación UI/UX: {str(exc)}"}


async def tester_node(state: FactoryState) -> FactoryState:
    task_id = state["task_id"]
    wt_manager = WorktreeManager()
    agent = TesterAgent()
    try:
        worktree_path = wt_manager.get_worktree_path(task_id)

        KanbanService.transition_task(
            task_id,
            TaskTransitionRequest(
                target_status=TaskStatus.TESTING,
                agent_role="tester",
                reason="Iniciando ejecución de pruebas en sandbox.",
            ),
        )

        verdict = await agent.run_tests(task_id, worktree_path)
        if not verdict.tests_passed:
            return {
                **state,
                "test_verdict": verdict.model_dump(),
                "error_message": f"Las pruebas de QA fallaron: {verdict.summary}",
            }

        return {
            **state,
            "status": TaskStatus.TESTING.value,
            "test_verdict": verdict.model_dump(),
            "error_message": None,
        }
    except Exception as exc:
        return {**state, "error_message": f"Fallo en pruebas QA: {str(exc)}"}


async def reviewer_node(state: FactoryState) -> FactoryState:
    task_id = state["task_id"]
    wt_manager = WorktreeManager()
    agent = ReviewerAgent()
    try:
        worktree_path = wt_manager.get_worktree_path(task_id)
        profile = load_profile_from_repo(worktree_path)

        # 1. Validación de directivas de rutas protegidas declaradas en el perfil
        changed_files = await wt_manager.get_changed_files(task_id, base_branch=profile.base_branch)
        violations = check_protected_paths(profile, changed_files)
        if violations:
            err_msg = (
                f"Violación de arquitectura: se han modificado rutas protegidas en {profile.project_name} "
                f"({', '.join(violations)})."
            )
            return {
                **state,
                "error_message": err_msg,
            }

        # 2. Análisis de diff y escaneo de secretos
        diff_text = await wt_manager.get_diff(task_id, base_branch=profile.base_branch)
        verdict = await agent.review_task(
            task_id=task_id,
            diff_text=diff_text,
            acceptance_criteria=state.get("acceptance_criteria", []),
            data_classification=state.get("data_classification", "approved_diff"),
        )

        if verdict.has_secrets:
            return {
                **state,
                "review_verdict": verdict.model_dump(),
                "error_message": f"Se han detectado {verdict.secret_count} secretos en el diff. Tarea bloqueada.",
            }

        if not verdict.is_approved:
            return {
                **state,
                "review_verdict": verdict.model_dump(),
                "error_message": f"Revisor rechazó los cambios: {verdict.recommendation_for_human}",
            }

        KanbanService.transition_task(
            task_id,
            TaskTransitionRequest(
                target_status=TaskStatus.REVIEW,
                agent_role="reviewer",
                reason=f"Revisión de seguridad y código superada. {verdict.recommendation_for_human}",
                metadata={"risk_assessment": verdict.risk_assessment},
            ),
        )

        return {
            **state,
            "status": TaskStatus.REVIEW.value,
            "review_verdict": verdict.model_dump(),
            "error_message": None,
        }
    except Exception as exc:
        return {**state, "error_message": f"Fallo en revisor: {str(exc)}"}


async def error_node(state: FactoryState) -> FactoryState:
    task_id = state["task_id"]
    error_msg = state.get("error_message") or "Error durante la ejecución multiagente."

    KanbanService.transition_task(
        task_id,
        TaskTransitionRequest(
            target_status=TaskStatus.BLOCKED,
            agent_role="coordinator",
            reason=error_msg,
        ),
    )

    try:
        from software_factory.kanban.incidents import IncidentService, IncidentCreate
        category = "policy_violation" if "política" in error_msg.lower() else "runtime_error"
        if "secreto" in error_msg.lower():
            category = "secret_detected"
        severity = "critical" if category in ("policy_violation", "secret_detected") else "high"

        IncidentService.create_incident(
            IncidentCreate(
                task_id=task_id,
                title=f"Bloqueo en tarea {task_id}: {error_msg[:70]}",
                description=error_msg,
                severity=severity,
                category=category,
                reported_by="LangGraph Coordinator",
            )
        )
    except Exception:
        pass

    return {**state, "status": TaskStatus.BLOCKED.value}


# --- 2. Enrutadores Condicionales ---

def route_analyst(state: FactoryState) -> str:
    return "error_node" if state.get("error_message") else "architect_node"

def route_architect(state: FactoryState) -> str:
    return "error_node" if state.get("error_message") else "developer_node"

def route_developer(state: FactoryState) -> str:
    return "error_node" if state.get("error_message") else "uiux_node"

def route_uiux(state: FactoryState) -> str:
    return "error_node" if state.get("error_message") else "tester_node"

def route_tester(state: FactoryState) -> str:
    return "error_node" if state.get("error_message") else "reviewer_node"

def route_reviewer(state: FactoryState) -> str:
    # Si todo es exitoso, termina en REVIEW esperando la barrera humana
    return "error_node" if state.get("error_message") else END


# --- 3. Construcción del Grafo ---

def build_factory_graph():
    graph = StateGraph(FactoryState)

    graph.add_node("analyst_node", analyst_node)
    graph.add_node("architect_node", architect_node)
    graph.add_node("developer_node", developer_node)
    graph.add_node("uiux_node", uiux_node)
    graph.add_node("tester_node", tester_node)
    graph.add_node("reviewer_node", reviewer_node)
    graph.add_node("error_node", error_node)

    graph.add_edge(START, "analyst_node")
    graph.add_conditional_edges("analyst_node", route_analyst)
    graph.add_conditional_edges("architect_node", route_architect)
    graph.add_conditional_edges("developer_node", route_developer)
    graph.add_conditional_edges("uiux_node", route_uiux)
    graph.add_conditional_edges("tester_node", route_tester)
    graph.add_conditional_edges("reviewer_node", route_reviewer)
    graph.add_edge("error_node", END)

    return graph.compile()


factory_graph = build_factory_graph()


async def run_analyst_flow(task_id: str) -> FactoryState:
    """Ejecuta solo la fase de análisis inicial para clarificar criterios."""
    task = KanbanService.get_task(task_id)
    state: FactoryState = {
        "task_id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status.value,
        "data_classification": task.data_classification.value,
        "acceptance_criteria": task.acceptance_criteria,
    }
    res = await analyst_node(state)
    if res.get("error_message"):
        return await error_node(res)
    return res


async def run_full_cycle(task_id: str) -> FactoryState:
    """Ejecuta el ciclo completo asistido hasta dejar la tarea lista en REVIEW."""
    task = KanbanService.get_task(task_id)
    initial_state: FactoryState = {
        "task_id": task.id,
        "title": task.title,
        "description": task.description,
        "status": task.status.value,
        "data_classification": task.data_classification.value,
        "acceptance_criteria": task.acceptance_criteria,
        "iteration_count": 0,
        "max_iterations": 5,
        "error_message": None,
    }

    final_state = await factory_graph.ainvoke(initial_state)
    return final_state
