"""Pruebas de la configuración y políticas de entorno."""

from software_factory.settings import Settings


def test_settings_defaults():
    s = Settings()
    assert s.factory_host == "127.0.0.1"
    assert s.factory_port == 8000
    assert s.fcc_enabled is True
    assert s.foundry_local_enabled is False  # Restricción: deshabilitado por defecto
    assert s.azure_ai_endpoint is None
