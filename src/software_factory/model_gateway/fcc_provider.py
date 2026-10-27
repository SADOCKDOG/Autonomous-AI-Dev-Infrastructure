"""Adaptadores para el proxy Free Claude Code (FCC)."""

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


class FCCResponsesProvider:
    """Adaptador de FCC para la interfaz OpenAI / Responses."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8082/v1",
        token: str | None = None,
        timeout: float = 60.0,
        is_local_backend: bool = False,
        client: httpx.AsyncClient | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._is_local_backend = is_local_backend
        self._client = client

    @property
    def provider_name(self) -> str:
        return "fcc_responses"

    @property
    def is_local(self) -> bool:
        # Aunque el proxy corre en localhost, sus backends suelen ser APIs externas.
        # Solo se considera local si se configura explícitamente con un backend 100% local.
        return self._is_local_backend

    def _get_headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{self.base_url}{path}"
        headers = {**self._get_headers(), **kwargs.pop("headers", {})}
        
        try:
            if self._client:
                return await self._client.request(method, url, headers=headers, timeout=self.timeout, **kwargs)
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                return await c.request(method, url, headers=headers, **kwargs)
        except httpx.TimeoutException as exc:
            raise TimeoutError(f"Timeout esperando respuesta de FCC en {url}", provider=self.provider_name) from exc
        except httpx.ConnectError as exc:
            raise ProviderError(
                f"No se pudo conectar al proxy FCC en {self.base_url}. ¿Está fcc-server en ejecución?",
                provider=self.provider_name,
            ) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Error de red en FCC: {str(exc)}", provider=self.provider_name) from exc

    async def generate(self, request: ModelRequest) -> ModelResponse:
        start_time = time.perf_counter()
        
        payload = {
            "model": request.model,
            "messages": [m.model_dump(exclude_none=True) for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": False,
        }

        resp = await self._request("POST", "/chat/completions", json=payload)
        latency_ms = (time.perf_counter() - start_time) * 1000

        if resp.status_code == 401 or resp.status_code == 403:
            raise AuthenticationError("Credenciales o token rechazado por FCC", provider=self.provider_name, status_code=resp.status_code)
        if resp.status_code == 429:
            raise RateLimitError("Límite de tasa excedido en el proveedor de FCC", provider=self.provider_name, status_code=429)
        if resp.is_error:
            raise ProviderError(f"Error HTTP {resp.status_code}: {resp.text}", provider=self.provider_name, status_code=resp.status_code)

        data = resp.json()
        choice = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "")
        finish_reason = choice.get("finish_reason", "stop")

        raw_usage = data.get("usage", {})
        usage = ModelUsage(
            prompt_tokens=raw_usage.get("prompt_tokens", 0),
            completion_tokens=raw_usage.get("completion_tokens", 0),
            total_tokens=raw_usage.get("total_tokens", 0),
        )

        return ModelResponse(
            provider=self.provider_name,
            model=request.model,
            content=content,
            finish_reason=finish_reason,
            usage=usage,
            latency_ms=round(latency_ms, 2),
        )

    async def healthcheck(self) -> ProviderHealth:
        start_time = time.perf_counter()
        try:
            resp = await self._request("GET", "/models")
            latency_ms = (time.perf_counter() - start_time) * 1000
            if resp.status_code == 200:
                return ProviderHealth(
                    provider=self.provider_name,
                    status="healthy",
                    latency_ms=round(latency_ms, 2),
                    details="Proxy FCC en línea",
                )
            return ProviderHealth(
                provider=self.provider_name,
                status="degraded",
                latency_ms=round(latency_ms, 2),
                details=f"HTTP {resp.status_code}",
            )
        except Exception as exc:
            return ProviderHealth(
                provider=self.provider_name,
                status="unhealthy",
                details=str(exc),
            )

    async def capabilities(self, model: str) -> ModelCapabilities:
        return ModelCapabilities(
            model=model,
            supports_tools=True,
            supports_vision=False,
            supports_streaming=True,
            supports_json_schema=True,
            context_window=32768,
        )


class FCCAnthropicProvider:
    """Adaptador de FCC para la interfaz Anthropic Messages."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8082/v1",
        token: str | None = None,
        timeout: float = 60.0,
        is_local_backend: bool = False,
        client: httpx.AsyncClient | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._is_local_backend = is_local_backend
        self._client = client

    @property
    def provider_name(self) -> str:
        return "fcc_anthropic"

    @property
    def is_local(self) -> bool:
        return self._is_local_backend

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        if self.token:
            headers["x-api-key"] = self.token
        return headers

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        url = f"{self.base_url}{path}"
        headers = {**self._get_headers(), **kwargs.pop("headers", {})}
        try:
            if self._client:
                return await self._client.request(method, url, headers=headers, timeout=self.timeout, **kwargs)
            async with httpx.AsyncClient(timeout=self.timeout) as c:
                return await c.request(method, url, headers=headers, **kwargs)
        except httpx.TimeoutException as exc:
            raise TimeoutError(f"Timeout en FCC Anthropic {url}", provider=self.provider_name) from exc
        except httpx.ConnectError as exc:
            raise ProviderError(f"No se pudo conectar a FCC Anthropic en {self.base_url}", provider=self.provider_name) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Error de red en FCC Anthropic: {str(exc)}", provider=self.provider_name) from exc

    async def generate(self, request: ModelRequest) -> ModelResponse:
        start_time = time.perf_counter()

        system_prompt = ""
        user_messages: list[dict[str, str]] = []
        for m in request.messages:
            if m.role == "system":
                system_prompt += f"{m.content}\n"
            else:
                user_messages.append({"role": m.role, "content": m.content})

        payload = {
            "model": request.model,
            "system": system_prompt.strip() if system_prompt else None,
            "messages": user_messages,
            "max_tokens": request.max_tokens or 4096,
            "temperature": request.temperature,
        }

        resp = await self._request("POST", "/messages", json=payload)
        latency_ms = (time.perf_counter() - start_time) * 1000

        if resp.status_code == 429:
            raise RateLimitError("Rate limit en FCC Anthropic", provider=self.provider_name, status_code=429)
        if resp.is_error:
            raise ProviderError(f"Error HTTP {resp.status_code}: {resp.text}", provider=self.provider_name, status_code=resp.status_code)

        data = resp.json()
        content_blocks = data.get("content", [])
        text_content = "".join(b.get("text", "") for b in content_blocks if b.get("type") == "text")

        raw_usage = data.get("usage", {})
        usage = ModelUsage(
            prompt_tokens=raw_usage.get("input_tokens", 0),
            completion_tokens=raw_usage.get("output_tokens", 0),
            total_tokens=raw_usage.get("input_tokens", 0) + raw_usage.get("output_tokens", 0),
        )

        return ModelResponse(
            provider=self.provider_name,
            model=request.model,
            content=text_content,
            finish_reason=data.get("stop_reason", "end_turn"),
            usage=usage,
            latency_ms=round(latency_ms, 2),
        )

    async def healthcheck(self) -> ProviderHealth:
        start_time = time.perf_counter()
        try:
            resp = await self._request("GET", "/models")
            latency_ms = (time.perf_counter() - start_time) * 1000
            return ProviderHealth(
                provider=self.provider_name,
                status="healthy" if resp.status_code == 200 else "degraded",
                latency_ms=round(latency_ms, 2),
            )
        except Exception as exc:
            return ProviderHealth(provider=self.provider_name, status="unhealthy", details=str(exc))

    async def capabilities(self, model: str) -> ModelCapabilities:
        return ModelCapabilities(
            model=model,
            supports_tools=True,
            supports_vision=True,
            supports_streaming=True,
            supports_json_schema=True,
            context_window=200000,
        )
