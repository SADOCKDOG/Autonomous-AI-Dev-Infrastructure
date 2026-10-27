"""Pruebas exhaustivas para el Model Gateway, adaptadores y políticas de datos."""

import pytest
import httpx
from software_factory.model_gateway.base import (
    ChatMessage,
    ModelRequest,
    PolicyViolationError,
    ProviderDisabledError,
)
from software_factory.model_gateway.registry import ModelGateway
from software_factory.model_gateway.fcc_provider import FCCResponsesProvider, FCCAnthropicProvider
from software_factory.model_gateway.azure_foundry import AzureFoundryProvider
from software_factory.model_gateway.foundry_local import FoundryLocalProvider
from software_factory.model_gateway.policy import ModelPolicyEngine


@pytest.mark.asyncio
async def test_fcc_responses_provider_success():
    """Simula una respuesta exitosa compatible con OpenAI de fcc-server."""
    mock_response_data = {
        "id": "chatcmpl-123",
        "choices": [
            {
                "message": {"role": "assistant", "content": "Plan de arquitectura generado por FCC."},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 50, "completion_tokens": 30, "total_tokens": 80},
    }

    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=mock_response_data)
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = FCCResponsesProvider(client=client)
        req = ModelRequest(
            messages=[ChatMessage(role="user", content="Diseña la arquitectura")],
            model="fcc-test-model",
        )
        res = await provider.generate(req)
        assert res.provider == "fcc_responses"
        assert res.content == "Plan de arquitectura generado por FCC."
        assert res.usage.total_tokens == 80
        assert res.latency_ms >= 0


@pytest.mark.asyncio
async def test_fcc_anthropic_provider_success():
    """Simula una respuesta exitosa en formato Anthropic Messages de fcc-server."""
    mock_data = {
        "content": [{"type": "text", "text": "Código generado por FCC Anthropic."}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 40, "output_tokens": 20},
    }

    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json=mock_data)
    )
    async with httpx.AsyncClient(transport=transport) as client:
        provider = FCCAnthropicProvider(client=client)
        req = ModelRequest(
            messages=[
                ChatMessage(role="system", content="Eres el desarrollador"),
                ChatMessage(role="user", content="Escribe una función"),
            ],
            model="claude-3-5-sonnet",
        )
        res = await provider.generate(req)
        assert res.provider == "fcc_anthropic"
        assert res.content == "Código generado por FCC Anthropic."
        assert res.usage.total_tokens == 60


@pytest.mark.asyncio
async def test_azure_foundry_mock_mode_without_credits():
    """Verifica que Azure Foundry opera en modo Mock sin consumir créditos ni fallar."""
    provider = AzureFoundryProvider(mock_mode=True)
    req = ModelRequest(
        messages=[ChatMessage(role="user", content="Test")],
        model="gpt-4o",
        task_id="TASK-001",
    )
    res = await provider.generate(req)
    assert res.provider == "azure_foundry"
    assert "[Azure Mock Response]" in res.content
    assert res.usage.total_tokens == 65


@pytest.mark.asyncio
async def test_foundry_local_strictly_disabled():
    """Garantiza que Foundry Local está deshabilitado y bloquea cualquier intento de descarga o inferencia."""
    provider = FoundryLocalProvider(enabled=False)
    health = await provider.healthcheck()
    assert health.status == "disabled"
    assert "0 descargas" in health.details

    req = ModelRequest(
        messages=[ChatMessage(role="user", content="Hola")],
        model="phi-3-mini",
    )
    with pytest.raises(ProviderDisabledError) as exc_info:
        await provider.generate(req)
    assert "no se permite la descarga de pesos" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_data_policy_local_only_blocks_remote():
    """Garantiza que una tarea marcada local_only jamás se envía a Azure o FCC remoto."""
    remote_provider = AzureFoundryProvider(mock_mode=True)
    req = ModelRequest(
        messages=[ChatMessage(role="user", content="Código confidencial")],
        model="any",
        data_classification="local_only",
    )

    with pytest.raises(PolicyViolationError) as exc_info:
        ModelPolicyEngine.validate_request(req, remote_provider)
    assert "local_only" in str(exc_info.value)


@pytest.mark.asyncio
async def test_data_policy_restricted_requires_human_approval():
    """Garantiza que una tarea con datos restringidos exige autorización humana."""
    remote_provider = FCCResponsesProvider()
    req = ModelRequest(
        messages=[ChatMessage(role="user", content="Contexto bancario")],
        model="any",
        data_classification="restricted",
        metadata={"human_approved": False},
    )

    with pytest.raises(PolicyViolationError) as exc_info:
        ModelPolicyEngine.validate_request(req, remote_provider)
    assert "aprobación humana" in str(exc_info.value).lower()

    # Si se autoriza expresamente, debe permitir el paso
    req.metadata["human_approved"] = True
    ModelPolicyEngine.validate_request(req, remote_provider)


@pytest.mark.asyncio
async def test_model_gateway_agent_routing():
    """Verifica que el gateway resuelve el proveedor adecuado según el rol del agente."""
    gateway = ModelGateway()
    # analyst -> fcc_anthropic por defecto en agents.yaml
    provider = gateway.resolve_provider_for_agent("analyst")
    assert provider.provider_name == "fcc_anthropic"

    # Verificar que healthcheck_all reporta todos los proveedores
    health = await gateway.healthcheck_all()
    assert "fcc_responses" in health
    assert "azure_foundry" in health
    assert "foundry_local" in health
    assert health["foundry_local"].status == "disabled"
