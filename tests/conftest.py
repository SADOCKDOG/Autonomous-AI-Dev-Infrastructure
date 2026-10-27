"""Configuración de fixtures para pruebas de pytest."""

import os
import tempfile
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from software_factory.settings import settings
from software_factory.persistence.database import init_db
from software_factory.api.main import app


@pytest.fixture(autouse=True)
def test_db_setup(monkeypatch):
    """Crea una base de datos SQLite aislada en un directorio temporal para cada test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_db_path = Path(tmpdir) / "test_factory.db"
        monkeypatch.setattr(settings, "database_url", f"sqlite:///{test_db_path}")
        init_db(test_db_path)
        yield test_db_path


@pytest.fixture
def client():
    """Cliente de test para llamadas HTTP a FastAPI."""
    with TestClient(app) as c:
        yield c
