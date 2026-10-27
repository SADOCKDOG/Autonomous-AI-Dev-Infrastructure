"""Adaptadores para el proxy Free Claude Code (FCC) con resolución automática para WSL2."""

import time
import socket
import struct
from pathlib import Path
from typing import Any
import httpx
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


def get_wsl_host_ip() -> str | None:
    """Detecta la IP del host Windows desde WSL2 leyendo la tabla de rutas del kernel."""
    route_file = Path("/proc/net/route")
    if not route_file.exists():
        return None
    try:
        with open(route_file, "r", encoding="utf-8") as f:
            for line in f:
                fields = line.strip().split()
                if len(fields) >= 3 and fields[1] == "00000000":
                    return socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))
    except Exception:
        pass
    return None


def resolve_loopback_for_wsl(url: str) -> str:
    """Si se ejecuta dentro de WSL2 y el destino es loopback, intenta resolver la IP del host Windows."""
    if "127.0.0.1" in url or "localhost" in url:
        host_ip = get_wsl_host_ip()
        if host_ip:
            try:
                with socket.create_connection(("127.0.0.1", 8082), timeout=0.1):
                    return url
            except OSError:
                return url.replace("127.0.0.1", host_ip).replace("localhost", host_ip)
    return url


class FCCAnthropicProvider:
    """Adaptador de FCC para la interfaz Anthropic Messages (/v1/messages)."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8082/v1",
        token: str | None = None,
        timeout: float = 240.0,
        is_local_backend: bool = False,
        client: httpx.AsyncClient | None = None,
    ):
        self._raw_base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._is_local_backend = is_local_backend
        self._client = client

    @property
    def base_url(self) -> str:
        return resolve_loopback_for_wsl(self._raw_base_url)

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
            "stream": False,
        }

        resp = await self._request("POST", "/messages", json=payload)
        latency_ms = (time.perf_counter() - start_time) * 1000

        if resp.status_code in (401, 403):
            raise AuthenticationError("Credenciales rechazadas por FCC (/v1/messages)", provider=self.provider_name, status_code=resp.status_code)
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
            if resp.status_code == 200:
                models_data = resp.json().get("data", [])
                return ProviderHealth(
                    provider=self.provider_name,
                    status="healthy",
                    latency_ms=round(latency_ms, 2),
                    details=f"Proxy FCC en línea ({len(models_data)} modelos disponibles)",
                )
            return ProviderHealth(
                provider=self.provider_name,
                status="degraded",
                latency_ms=round(latency_ms, 2),
                details=f"HTTP {resp.status_code}",
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


class FCCResponsesProvider:
    """Adaptador de FCC para la interfaz OpenAI Responses (/v1/responses)."""

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8082/v1",
        token: str | None = None,
        timeout: float = 240.0,
        is_local_backend: bool = False,
        client: httpx.AsyncClient | None = None,
    ):
        self._raw_base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._is_local_backend = is_local_backend
        self._client = client

    @property
    def base_url(self) -> str:
        return resolve_loopback_for_wsl(self._raw_base_url)

    @property
    def provider_name(self) -> str:
        return "fcc_responses"

    @property
    def is_local(self) -> bool:
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
            raise TimeoutError(f"Timeout en FCC Responses {url}", provider=self.provider_name) from exc
        except httpx.ConnectError as exc:
            raise ProviderError(f"No se pudo conectar a FCC Responses en {self.base_url}", provider=self.provider_name) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Error de red en FCC Responses: {str(exc)}", provider=self.provider_name) from exc

    async def generate(self, request: ModelRequest) -> ModelResponse:
        start_time = time.perf_counter()

        instructions = ""
        input_messages = []
        for m in request.messages:
            if m.role == "system":
                instructions += f"{m.content}\n"
            else:
                input_messages.append(m.content)

        payload = {
            "model": request.model,
            "instructions": instructions.strip() if instructions else None,
            "input": "\n".join(input_messages),
            "stream": True,
            "temperature": request.temperature,
            "max_output_tokens": request.max_tokens,
        }

        # Manejo de streaming SSE para /v1/responses
        url = f"{self.base_url}/responses"
        headers = self._get_headers()
        content = ""
        raw_usage: dict[str, Any] = {}

        try:
            if self._client:
                resp = await self._client.post(url, json=payload, headers=headers, timeout=self.timeout)
                if resp.is_error:
                    raise ProviderError(f"Error HTTP {resp.status_code}: {resp.text}", provider=self.provider_name, status_code=resp.status_code)
                if "data: " in resp.text:
                    for line in resp.text.splitlines():
                        if line.startswith("data: "):
                            line_data = line[6:].strip()
                            if line_data and line_data != "[DONE]":
                                try:
                                    chunk = json.loads(line_data)
                                    if "delta" in chunk:
                                        content += chunk["delta"].get("text", "")
                                    elif "text" in chunk:
                                        content += chunk["text"]
                                    if "usage" in chunk:
                                        raw_usage = chunk["usage"]
                                except Exception:
                                    pass
                else:
                    try:
                        data = resp.json()
                        choice_content = ""
                        if "choices" in data and len(data["choices"]) > 0:
                            choice_content = data["choices"][0].get("message", {}).get("content", "")
                        content = data.get("output", "") or data.get("text", "") or choice_content
                        if isinstance(content, list):
                            content = "".join(str(c) for c in content)
                        raw_usage = data.get("usage", {})
                    except Exception:
                        pass
            else:
                async with httpx.AsyncClient(timeout=self.timeout) as c:
                    async with c.stream("POST", url, json=payload, headers=headers) as stream_resp:
                        if stream_resp.is_error:
                            await stream_resp.aread()
                            raise ProviderError(f"Error HTTP {stream_resp.status_code}: {stream_resp.text}", provider=self.provider_name, status_code=stream_resp.status_code)
                        async for line in stream_resp.aiter_lines():
                            if line.startswith("data: "):
                                line_data = line[6:].strip()
                                if line_data and line_data != "[DONE]":
                                    try:
                                        chunk = json.loads(line_data)
                                        if "delta" in chunk:
                                            content += chunk["delta"].get("text", "")
                                        elif "text" in chunk:
                                            content += chunk["text"]
                                        if "usage" in chunk:
                                            raw_usage = chunk["usage"]
                                    except Exception:
                                        pass
        except httpx.TimeoutException as exc:
            raise TimeoutError(f"Timeout en FCC Responses {url}", provider=self.provider_name) from exc
        except httpx.ConnectError as exc:
            raise ProviderError(f"No se pudo conectar a FCC Responses en {self.base_url}", provider=self.provider_name) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"Error de red en FCC Responses: {str(exc)}", provider=self.provider_name) from exc

        latency_ms = (time.perf_counter() - start_time) * 1000
        usage = ModelUsage(
            prompt_tokens=raw_usage.get("input_tokens", 0),
            completion_tokens=raw_usage.get("output_tokens", 0),
            total_tokens=raw_usage.get("total_tokens", 0),
        )

        return ModelResponse(
            provider=self.provider_name,
            model=request.model,
            content=str(content),
            finish_reason="stop",
            usage=usage,
            latency_ms=round(latency_ms, 2),
        )

    async def healthcheck(self) -> ProviderHealth:
        start_time = time.perf_counter()
        try:
            resp = await self._request("GET", "/models")
            latency_ms = (time.perf_counter() - start_time) * 1000
            if resp.status_code == 200:
                models_data = resp.json().get("data", [])
                return ProviderHealth(
                    provider=self.provider_name,
                    status="healthy",
                    latency_ms=round(latency_ms, 2),
                    details=f"Proxy FCC en línea ({len(models_data)} modelos disponibles)",
                )
            return ProviderHealth(
                provider=self.provider_name,
                status="degraded",
                latency_ms=round(latency_ms, 2),
                details=f"HTTP {resp.status_code}",
            )
        except Exception as exc:
            return ProviderHealth(provider=self.provider_name, status="unhealthy", details=str(exc))

    async def capabilities(self, model: str) -> ModelCapabilities:
        return ModelCapabilities(
            model=model,
            supports_tools=True,
            supports_vision=False,
            supports_streaming=True,
            supports_json_schema=True,
            context_window=32768,
        )
