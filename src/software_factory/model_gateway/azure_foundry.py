"""Adaptador para Azure AI Foundry (conexión directa con soporte para Mock y Entra ID)."""

import time
import httpx
from typing import Any
from software_factory.model_gateway.base import (
    ModelProvider,
    ModelRequest,
    ModelResponse,
    ModelUsage,
    ProviderHealth,
    ModelCapabilities,
    ProviderError,
    TimeoutError,
    RateLimitError,
    AuthenticationError,
)


class AzureFoundryProvider:
    """Adaptador de inferencia directo hacia Azure AI Foundry."""

    def __init__(
        self,
        endpoint: str | None = None,
        deployment: str | None = None,
        api_key: str | None = None,
        mock_mode: bool = False,
        timeout: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ):
        self.endpoint = (endpoint or "").rstrip("/")
        self.deployment = deployment
        self.api_key = api_key
        self.mock_mode = mock_mode or not bool(endpoint and (api_key or deployment))
        self.timeout = timeout
        self._client = client

    @property
    def provider_name(self) -> str:
        return "azure_foundry"

    @property
    def is_local(self) -> bool:
        # Azure siempre es un servicio remoto
        return False

    async def generate(self, request: ModelRequest) -> ModelResponse:
        start_time = time.perf_counter()

        if self.mock_mode:
            # Modo Mock para cuando no hay créditos o en entorno de tests
            return ModelResponse(
                provider=self.provider_name,
                model=request.model or (self.deployment or "azure-mock"),
                content=f"[Azure Mock Response] Análisis completado para tarea '{request.task_id or 'N/A'}'",
                finish_reason="stop",
                usage=ModelUsage(prompt_tokens=40, completion_tokens=25, total_tokens=65),
                latency_ms=12.5,
            )

        if not self.endpoint or not self.deployment:
            raise AuthenticationError(
                "Faltan credenciales de Azure AI Foundry (AZURE_AI_ENDPOINT o AZURE_AI_MODEL_DEPLOYMENT)",
                provider=self.provider_name,
            )

        url = f"{self.endpoint}/openai/deployments/{self.deployment}/chat/completions?api-version=2024-06-01"
        headers = {
            "Content-Type": "application/json",
            "api-key": self.api_key or "",
        }
        payload = {
            "messages": [m.model_dump(exclude_none=True) for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        try:
            if self._client:
                resp = await self._client.post(url, json=payload, headers=headers, timeout=self.timeout)
            else:
                async with httpx.AsyncClient(timeout=self.timeout) as c:
                    resp = await c.post(url, json=payload, headers=headers)
        except httpx.TimeoutException as exc:
            raise TimeoutError("Timeout conectando con Azure AI Foundry", provider=self.provider_name) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Error de red con Azure: {str(exc)}", provider=self.provider_name) from exc

        latency_ms = (time.perf_counter() - start_time) * 1000

        if resp.status_code in (401, 403):
            raise AuthenticationError("Autenticación rechazada por Azure AI Foundry", provider=self.provider_name, status_code=resp.status_code)
        if resp.status_code == 429:
            raise RateLimitError("Cuota de TPM/RPM excedida en Azure AI Foundry", provider=self.provider_name, status_code=429)
        if resp.is_error:
            raise ProviderError(f"Error en Azure AI: {resp.status_code} {resp.text}", provider=self.provider_name, status_code=resp.status_code)

        data = resp.json()
        choice = data.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content", "")
        raw_usage = data.get("usage", {})

        return ModelResponse(
            provider=self.provider_name,
            model=self.deployment or request.model,
            content=content,
            finish_reason=choice.get("finish_reason", "stop"),
            usage=ModelUsage(
                prompt_tokens=raw_usage.get("prompt_tokens", 0),
                completion_tokens=raw_usage.get("completion_tokens", 0),
                total_tokens=raw_usage.get("total_tokens", 0),
            ),
            latency_ms=round(latency_ms, 2),
        )

    async def healthcheck(self) -> ProviderHealth:
        if self.mock_mode:
            return ProviderHealth(
                provider=self.provider_name,
                status="healthy",
                details="Modo simulado activo (sin consumo de créditos de Azure)",
            )
        return ProviderHealth(
            provider=self.provider_name,
            status="healthy" if self.endpoint else "unhealthy",
            details="Conectado a Azure AI Foundry" if self.endpoint else "Endpoint no configurado",
        )

    async def capabilities(self, model: str) -> ModelCapabilities:
        return ModelCapabilities(
            model=model or (self.deployment or "azure-default"),
            supports_tools=True,
            supports_vision=True,
            supports_streaming=True,
            supports_json_schema=True,
            context_window=128000,
        )
