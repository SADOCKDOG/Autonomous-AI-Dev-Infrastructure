"""Estado tipado para el grafo de orquestación de LangGraph."""

from typing import TypedDict, Any


class FactoryState(TypedDict, total=False):
    """Estado acumulativo compartido entre los nodos del grafo de la fábrica."""
    task_id: str
    title: str
    description: str
    status: str
    data_classification: str
    acceptance_criteria: list[str]
    analyst_summary: str | None
    suggested_priority: str | None
    functional_scope: list[str]
    error_message: str | None
    iteration_count: int
    max_iterations: int
    metadata: dict[str, Any]
