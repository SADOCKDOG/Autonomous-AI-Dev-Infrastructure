"""Configuración tipada de la aplicación."""

import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Ajustes de la Software Factory con validación Pydantic."""

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent.parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Entorno y servidor
    factory_host: str = Field(default="127.0.0.1", alias="FACTORY_HOST")
    factory_port: int = Field(default=8000, alias="FACTORY_PORT")
    factory_env: str = Field(default="development", alias="FACTORY_ENV")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Rutas base
    base_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent)
    data_dir: Path = Field(default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "data")

    # Persistencia
    database_url: str = Field(default="sqlite:///data/factory.db", alias="DATABASE_URL")

    # Azure AI Foundry
    azure_ai_endpoint: str | None = Field(default=None, alias="AZURE_AI_ENDPOINT")
    azure_ai_model_deployment: str | None = Field(default=None, alias="AZURE_AI_MODEL_DEPLOYMENT")
    azure_tenant_id: str | None = Field(default=None, alias="AZURE_TENANT_ID")
    azure_client_id: str | None = Field(default=None, alias="AZURE_CLIENT_ID")
    azure_client_secret: str | None = Field(default=None, alias="AZURE_CLIENT_SECRET")

    # Free Claude Code (FCC)
    fcc_enabled: bool = Field(default=True, alias="FCC_ENABLED")
    fcc_anthropic_base_url: str = Field(default="http://127.0.0.1:8082/v1", alias="FCC_ANTHROPIC_BASE_URL")
    fcc_responses_base_url: str = Field(default="http://127.0.0.1:8082/v1", alias="FCC_RESPONSES_BASE_URL")
    fcc_proxy_token: str | None = Field(default=None, alias="FCC_PROXY_TOKEN")
    fcc_timeout: float = Field(default=240.0, alias="FCC_TIMEOUT")

    # Foundry Local (deshabilitado inicialmente)
    foundry_local_enabled: bool = Field(default=False, alias="FOUNDRY_LOCAL_ENABLED")
    foundry_local_base_url: str = Field(default="http://127.0.0.1:5272/v1", alias="FOUNDRY_LOCAL_BASE_URL")
    foundry_local_model: str | None = Field(default=None, alias="FOUNDRY_LOCAL_MODEL")

    # Modelos por defecto
    model_analyst: str = Field(default="fcc-default", alias="MODEL_ANALYST")
    model_architect: str = Field(default="fcc-default", alias="MODEL_ARCHITECT")
    model_developer: str = Field(default="fcc-default", alias="MODEL_DEVELOPER")
    model_tester: str = Field(default="fcc-default", alias="MODEL_TESTER")
    model_reviewer: str = Field(default="fcc-default", alias="MODEL_REVIEWER")

    def get_sqlite_path(self) -> Path:
        """Extrae la ruta al fichero sqlite asegurando su directorio contenedor."""
        if self.database_url.startswith("sqlite:///"):
            rel_or_abs = self.database_url.replace("sqlite:///", "")
            path = Path(rel_or_abs)
            if not path.is_absolute():
                path = self.base_dir / path
            path.parent.mkdir(parents=True, exist_ok=True)
            return path
        return self.data_dir / "factory.db"


settings = Settings()
