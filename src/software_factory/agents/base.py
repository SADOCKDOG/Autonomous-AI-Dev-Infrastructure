"""Clase base para todos los agentes de la Software Factory."""

from typing import Any
from pydantic import BaseModel
from software_factory.model_gateway.registry import ModelGateway
from software_factory.model_gateway.base import ModelRequest, ModelResponse, ChatMessage


class BaseAgent:
    """Agente con rol específico, límites de ejecución y acceso al Model Gateway."""

    def __init__(self, role: str, gateway: ModelGateway | None = None):
        self.role = role
        self.gateway = gateway or ModelGateway()

    @property
    def provider(self):
        return self.gateway.resolve_provider_for_agent(self.role)

    async def invoke_model(
        self,
        messages: list[ChatMessage],
        model: str | None = None,
        task_id: str | None = None,
        data_classification: str = "project_context",
        max_tokens: int = 4096,
        temperature: float = 0.2,
    ) -> ModelResponse:
        # Resolver nombre de modelo según configuración
        target_model = model or getattr(
            self.gateway, f"model_{self.role}", "kilo/kilo-auto/free"
        )
        
        req = ModelRequest(
            messages=messages,
            model=target_model,
            task_id=task_id,
            agent_role=self.role,
            data_classification=data_classification,  # type: ignore
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return await self.gateway.generate(req, provider_name=self.provider.provider_name)
