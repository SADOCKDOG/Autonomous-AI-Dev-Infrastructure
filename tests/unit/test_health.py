"""Pruebas del endpoint /health."""

from fastapi.testclient import TestClient


def test_health_endpoint_ok(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"
    assert data["database"] == "ok"
    assert "timestamp" in data
