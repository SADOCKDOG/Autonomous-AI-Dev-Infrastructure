"""Pruebas del endpoint /health."""

from fastapi.testclient import TestClient


def test_health_endpoint_ok(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert data["database"] == "ok"
    assert "providers" in data
    assert "fcc_responses" in data["providers"]
    assert "azure_foundry" in data["providers"]
    assert "foundry_local" in data["providers"]
    assert "timestamp" in data
