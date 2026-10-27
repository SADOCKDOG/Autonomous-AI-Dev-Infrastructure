"""Modelos de datos para el sistema de perfiles de proyecto."""

from enum import Enum
from typing import Any
import shlex
from pydantic import BaseModel, Field, field_validator


class ProjectArchetype(str, Enum):
    """Arquetipos de arquitectura de software soportados por la factoría."""
    MOBILE_PWA = "mobile_pwa"
    DESKTOP_TAURI = "desktop_tauri"
    BACKEND_API = "backend_api"
    WEB_SPA = "web_spa"
    PYTHON_SERVICE = "python_service"
    GENERIC = "generic"


class UIUXMode(str, Enum):
    """Modo de gobernanza UI/UX aplicable al proyecto."""
    NONE = "none"
    ADVISORY = "advisory"
    STRICT = "strict"


class ProjectProfile(BaseModel):
    """Perfil declarativo de configuración de un repositorio para la Software Factory."""

    project_name: str = Field(
        default="unknown-project",
        description="Nombre identificativo del proyecto o repositorio.",
    )
    archetype: ProjectArchetype = Field(
        default=ProjectArchetype.GENERIC,
        description="Arquetipo arquitectónico del proyecto.",
    )
    base_branch: str = Field(
        default="master",
        description="Rama base canónica contra la que se crean worktrees y diffs.",
    )
    test_command: list[str] = Field(
        default_factory=lambda: ["pytest", "-q"],
        description="Comando para ejecutar la suite de pruebas automatizadas.",
    )
    lint_command: list[str] | None = Field(
        default=None,
        description="Comando opcional de linting o validación estática.",
    )
    build_command: list[str] | None = Field(
        default=None,
        description="Comando opcional de compilación o build.",
    )
    uiux_mode: UIUXMode = Field(
        default=UIUXMode.ADVISORY,
        description="Modo de evaluación de diseño y tokens de interfaz.",
    )
    design_tokens_path: str | None = Field(
        default=None,
        description="Ruta relativa al archivo de tokens o estilos canónicos del proyecto.",
    )
    protected_paths: list[str] = Field(
        default_factory=list,
        description="Patrones glob de archivos o rutas protegidas cuya modificación está restringida.",
    )
    environment: dict[str, str] = Field(
        default_factory=dict,
        description="Variables de entorno específicas a inyectar en la ejecución de comandos.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Metadatos arbitrarios adicionales del proyecto.",
    )

    @field_validator("test_command", "lint_command", "build_command", mode="before")
    @classmethod
    def _parse_command_list(cls, val: Any) -> list[str] | None:
        """Permite que el comando se especifique como string o como lista de tokens."""
        if val is None:
            return None
        if isinstance(val, str):
            val = val.strip()
            if not val:
                return []
            return shlex.split(val)
        if isinstance(val, list):
            return [str(item) for item in val]
        return val
