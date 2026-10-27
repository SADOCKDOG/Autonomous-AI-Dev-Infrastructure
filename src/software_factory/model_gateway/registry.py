"""Registro y orquestación central de proveedores (ModelGateway)."""

import yaml
from pathlib import Path
from software_factory.settings import settings
from software_factory.model_gateway.base import (
    ModelProvider,
    ModelRequest,
    ModelResponse,
    ProviderHealth,
    ProviderError,
    ProviderDisabledError,
    PolicyViolationError,
)
from software_factory.model_gateway.policy import ModelPolicyEngine
from software_factory.model_gateway.fcc_provider import FCCResponsesProvider, FCCAnthropicProvider
from software_factory.model_gateway.azure_foundry import AzureFoundryProvider
from software_factory.model_gateway.foundry_local import FoundryLocalProvider


class ModelGateway:
    """Gateway agnóstico que enruta peticiones a proveedores según rol, agente y política."""

    def __init__(self, config_path: Path | None = None):
        self._providers: dict[str, ModelProvider] = {}
        self._agent_provider_map: dict[str, str] = {}
        self._init_providers()
        self._load_agent_mappings(config_path)

    def _init_providers(self) -> None:
        # 1. FCC Proxy (Proveedor activo para pruebas iniciales sin créditos de Azure)
        self._providers["fcc_responses"] = FCCResponsesProvider(
            base_url=settings.fcc_responses_base_url,
            token=settings.fcc_proxy_token,
        )
        self._providers["fcc_anthropic"] = FCCAnthropicProvider(
            base_url=settings.fcc_anthropic_base_url,
            token=settings.fcc_proxy_token,
        )

        # 2. Azure AI Foundry (Modo mock si no hay créditos configurados)
        self._providers["azure_foundry"] = AzureFoundryProvider(
            endpoint=settings.azure_ai_endpoint,
            deployment=settings.azure_ai_model_deployment,
            api_key=settings.azure_client_secret,
            mock_mode=bool(not settings.azure_ai_endpoint),
        )

        # 3. Microsoft Foundry Local (Estrictamente deshabilitado sin descargas de modelos)
        self._providers["foundry_local"] = FoundryLocalProvider(
            base_url=settings.foundry_local_base_url,
            enabled=settings.foundry_local_enabled,
        )

    def _load_agent_mappings(self, config_path: Path | None) -> None:
        path = config_path or (settings.base_dir / "config" / "agents.yaml")
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    agents = data.get("agents", {})
                    for role, conf in agents.items():
                        self._agent_provider_map[role] = conf.get("provider", "fcc_responses")
            except Exception:
                pass

    def register_provider(self, name: str, provider: ModelProvider) -> None:
        self._providers[name] = provider

    def get_provider(self, name: str) -> ModelProvider:
        if name not in self._providers:
            raise ProviderError(f"Proveedor '{name}' no registrado en el gateway.", provider="gateway")
        return self._providers[name]

    def resolve_provider_for_agent(self, agent_role: str | None) -> ModelProvider:
        provider_name = self._agent_provider_map.get(agent_role or "", "fcc_responses")
        return self.get_provider(provider_name)

    async def generate(self, request: ModelRequest, provider_name: str | None = None) -> ModelResponse:
        """Punto de entrada principal para inferencia con validación de política y auditoría."""
        if provider_name:
            provider = self.get_provider(provider_name)
        elif request.agent_role:
            provider = self.resolve_provider_for_agent(request.agent_role)
        else:
            provider = self.get_provider("fcc_responses")

        # 1. Validación estricta de política de datos
        ModelPolicyEngine.validate_request(request, provider)

        # 2. Invocación del proveedor
        return await provider.generate(request)

    async def healthcheck_all(self) -> dict[str, ProviderHealth]:
        results: dict[str, ProviderHealth] = {}
        for name, prov in self._providers.items():
            results[name] = await prov.healthcheck()
        return results
