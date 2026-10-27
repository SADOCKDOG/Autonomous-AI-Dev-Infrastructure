"""Script de verificación en vivo de FCC Proxy desde WSL2."""

import asyncio
from software_factory.model_gateway.registry import ModelGateway
from software_factory.model_gateway.base import ModelRequest, ChatMessage


async def main():
    gw = ModelGateway()
    print("--- 1. Healthcheck de Proveedores ---")
    health = await gw.healthcheck_all()
    for name, res in health.items():
        print(f"[{name}] status={res.status} | latency={res.latency_ms}ms | details={res.details}")

    print("\n--- 2. Petición inocua de prueba a FCC Anthropic (/v1/messages) ---")
    anthropic_provider = gw.get_provider("fcc_anthropic")
    req = ModelRequest(
        messages=[
            ChatMessage(role="user", content="Responde solo: 'FCC_OPERATIVO'")
        ],
        model="kilo/kilo-auto/free",
        max_tokens=20,
        temperature=0.0,
    )
    try:
        response = await anthropic_provider.generate(req)
        print(f"Respuesta recibida ({response.latency_ms} ms): {response.content.strip()}")
        print(f"Tokens usados: {response.usage.total_tokens}")
    except Exception as exc:
        print(f"Excepcion en peticion real: {exc}")


if __name__ == "__main__":
    asyncio.run(main())
