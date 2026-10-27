"""Adaptador para Microsoft Foundry Local (deshabilitado en esta fase, sin descarga de modelos)."""

from software_factory.model_gateway.base import (
    ModelProvider,
    ModelRequest,
    ModelResponse,
    ProviderHealth,
    ModelCapabilities,
    ProviderDisabledError,
)


class FoundryLocalProvider:
    """Adaptador para inferencia local con Microsoft Foundry Local."""

    def __init__(self, base_url: str = "http://127.0.0.1:5272/v1", enabled: bool = False):
        self.base_url = base_url
        self.enabled = enabled

    @property
    def provider_name(self) -> str:
        return "foundry_local"

    @property
    def is_local(self) -> bool:
        # Inferencia 100% en el equipo local
        return True

    async def generate(self, request: ModelRequest) -> ModelResponse:
        if not self.enabled:
            raise ProviderDisabledError(
                "Microsoft Foundry Local está deshabilitado en esta fase. "
                "No se permite la descarga de pesos de modelos sin autorización previa.",
                provider=self.provider_name,
            )
        raise NotImplementedError("Runtime de Foundry Local pendiente de certificación en Hito posterior.")

    async def healthcheck(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.provider_name,
            status="disabled",
            details="Deshabilitado por política: 0 descargas de modelos en esta fase.",
        )

    async def capabilities(self, model: str) -> ModelCapabilities:
        return ModelCapabilities(
            model=model,
            supports_tools=False,
            supports_vision=False,
            supports_streaming=True,
            supports_json_schema=False,
            context_window=4096,
        )
