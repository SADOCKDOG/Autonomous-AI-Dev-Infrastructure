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
    """Adaptador de inferencia directo hacia Azure AI Foundry (Microsoft Foundry Sdog Farm)."""

    def __init__(
        self,
        endpoint: str | None = None,
        deployment: str | None = None,
        api_key: str | None = None,
        tenant_id: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
        mock_mode: bool = False,
        timeout: float = 60.0,
        client: httpx.AsyncClient | None = None,
    ):
        self.endpoint = (endpoint or "").rstrip("/")
        self.deployment = deployment
        self.api_key = api_key
        self.tenant_id = tenant_id or "sadogfarm.onmicrosoft.com"
        self.client_id = client_id
        self.client_secret = client_secret
        has_credentials = bool(api_key or (client_id and client_secret))
        self.mock_mode = mock_mode or not bool(endpoint and (has_credentials or deployment))
        self.timeout = timeout
        self._client = client
        self._cached_bearer_token: str | None = None
        self._token_expires_at: float = 0.0

    @property
    def provider_name(self) -> str:
        return "azure_foundry"

    @property
    def is_local(self) -> bool:
        # Azure siempre es un servicio remoto
        return False

    async def _get_auth_headers(self) -> dict[str, str]:
        """Resuelve cabeceras mediante API key directa o token OAuth 2.0 de Microsoft Entra ID."""
        if self.api_key:
            return {"api-key": self.api_key}

        if self.client_id and self.client_secret and self.tenant_id:
            now = time.time()
            if self._cached_bearer_token and now < (self._token_expires_at - 60):
                return {"Authorization": f"Bearer {self._cached_bearer_token}"}

            token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
            data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "https://cognitiveservices.azure.com/.default",
            }
            try:
                if self._client:
                    resp = await self._client.post(token_url, data=data, timeout=self.timeout)
                else:
                    async with httpx.AsyncClient(timeout=self.timeout) as c:
                        resp = await c.post(token_url, data=data)

                if resp.is_success:
                    tok_data = resp.json()
                    self._cached_bearer_token = tok_data.get("access_token")
                    expires_in = tok_data.get("expires_in", 3600)
                    self._token_expires_at = now + expires_in
                    return {"Authorization": f"Bearer {self._cached_bearer_token}"}
                else:
                    raise AuthenticationError(
                        f"Error autenticando con Microsoft Entra ID ({self.tenant_id}): HTTP {resp.status_code}",
                        provider=self.provider_name,
                        status_code=resp.status_code,
                    )
            except Exception as exc:
                if isinstance(exc, AuthenticationError):
                    raise
                raise AuthenticationError(
                    f"Fallo en handshake de tokens con Microsoft Entra ID: {exc}",
                    provider=self.provider_name,
                ) from exc

        return {}

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
        auth_headers = await self._get_auth_headers()
        headers = {
            "Content-Type": "application/json",
            **auth_headers,
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
                details=f"Modo simulado activo para Microsoft Foundry Sdog Farm (Tenant: {self.tenant_id})",
            )
        return ProviderHealth(
            provider=self.provider_name,
            status="healthy" if self.endpoint else "unhealthy",
            details=f"Conectado a Microsoft Foundry Sdog Farm ({self.tenant_id})" if self.endpoint else "Endpoint no configurado",
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
