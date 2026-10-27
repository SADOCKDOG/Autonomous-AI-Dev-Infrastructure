"""Estado tipado para el grafo de orquestación completo de LangGraph."""

from typing import TypedDict, Any


class FactoryState(TypedDict, total=False):
    """Estado compartido entre todos los agentes de la Software Factory."""
    task_id: str
    title: str
    description: str
    status: str
    data_classification: str
    acceptance_criteria: list[str]
    analyst_summary: str | None
    suggested_priority: str | None
    functional_scope: list[str]
    architect_plan: dict[str, Any] | None
    developer_result: dict[str, Any] | None
    uiux_verdict: dict[str, Any] | None
    test_verdict: dict[str, Any] | None
    review_verdict: dict[str, Any] | None
    error_message: str | None
    iteration_count: int
    max_iterations: int
    metadata: dict[str, Any]
