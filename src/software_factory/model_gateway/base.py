"""Tipos base y protocolo para proveedores de modelos del Model Gateway."""

from typing import Protocol, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime, timezone


class ProviderError(Exception):
    """Error base de comunicación con un proveedor."""
    def __init__(self, message: str, provider: str, status_code: int | None = None):
        super().__init__(f"[{provider}] {message}")
        self.provider = provider
        self.status_code = status_code


class ProviderDisabledError(ProviderError):
    """El proveedor está configurado como deshabilitado."""
    pass


class PolicyViolationError(Exception):
    """Violación de la política de datos o seguridad."""
    pass


class TimeoutError(ProviderError):
    """Timeout en la respuesta del proveedor."""
    pass


class RateLimitError(ProviderError):
    """Límite de tasa (429) alcanzado en el proveedor."""
    pass


class AuthenticationError(ProviderError):
    """Fallo de autenticación (401/403) con el proveedor."""
    pass


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None


class ModelRequest(BaseModel):
    messages: list[ChatMessage]
    model: str
    temperature: float = 0.2
    max_tokens: int | None = 4096
    stream: bool = False
    task_id: str | None = None
    agent_role: str | None = None
    data_classification: Literal["local_only", "approved_remote", "restricted"] = "approved_remote"
    metadata: dict[str, Any] = Field(default_factory=dict)


class ModelUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_estimated_usd: float | None = None


class ModelResponse(BaseModel):
    provider: str
    model: str
    content: str
    finish_reason: str = "stop"
    usage: ModelUsage = Field(default_factory=ModelUsage)
    latency_ms: float = 0.0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ProviderHealth(BaseModel):
    provider: str
    status: Literal["healthy", "degraded", "unhealthy", "disabled"]
    latency_ms: float | None = None
    details: str = ""


class ModelCapabilities(BaseModel):
    model: str
    supports_tools: bool = False
    supports_vision: bool = False
    supports_streaming: bool = True
    supports_json_schema: bool = False
    context_window: int = 8192


class ModelProvider(Protocol):
    """Protocolo obligatorio para todos los adaptadores de inferencia."""

    @property
    def provider_name(self) -> str:
        ...

    @property
    def is_local(self) -> bool:
        """Indica si la inferencia se ejecuta estrictamente en la máquina local."""
        ...

    async def generate(self, request: ModelRequest) -> ModelResponse:
        ...

    async def healthcheck(self) -> ProviderHealth:
        ...

    async def capabilities(self, model: str) -> ModelCapabilities:
        ...
