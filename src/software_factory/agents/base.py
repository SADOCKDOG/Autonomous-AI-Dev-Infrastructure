"""Clase base para todos los agentes de la Software Factory."""

from typing import Any, Optional, Tuple
from pydantic import BaseModel
from software_factory.model_gateway.registry import ModelGateway
from software_factory.model_gateway.base import ModelRequest, ModelResponse, ChatMessage
from software_factory.agents.policy_manager import PolicyManager


class BaseAgent:
    """Agente con rol específico, límites de ejecución, políticas normativas y acceso al Model Gateway."""

    def __init__(self, role: str, gateway: ModelGateway | None = None):
        self.role = role
        self.gateway = gateway or ModelGateway()

    @property
    def provider(self):
        return self.gateway.resolve_provider_for_agent(self.role)

    @property
    def policy_info(self) -> Tuple[str, str]:
        """Retorna el contenido y el hash SHA-256 de la directiva de rol obligatoria."""
        return PolicyManager.load_role_policy(self.role)

    def get_consolidated_system_prompt(
        self,
        role_schema_prompt: Optional[str] = None,
        project_context: Optional[str] = None,
        project_key: Optional[str] = None,
        design_tokens_context: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Obtiene el prompt de sistema consolidado (Directiva de Rol + Contexto Proyecto + Esquema JSON).
        Retorna:
            Tuple[str, str]: (prompt_completo, policy_sha256)
        """
        return PolicyManager.build_consolidated_prompt(
            role=self.role,
            role_schema_prompt=role_schema_prompt,
            project_context=project_context,
            project_key=project_key,
            design_tokens_context=design_tokens_context,
        )

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
