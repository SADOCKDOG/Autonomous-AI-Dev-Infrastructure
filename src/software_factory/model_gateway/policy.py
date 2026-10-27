"""Motor de validación de políticas de datos y seguridad para el Model Gateway."""

from typing import Any
from software_factory.model_gateway.base import (
    ModelRequest,
    ModelProvider,
    PolicyViolationError,
)


class ModelPolicyEngine:
    """Valida que ninguna solicitud viole las fronteras de datos definidas."""

    @staticmethod
    def validate_request(request: ModelRequest, provider: ModelProvider) -> None:
        classification = request.data_classification

        # 1. Regla: local_only prohíbe terminantemente proveedores no locales
        if classification == "local_only" and not provider.is_local:
            raise PolicyViolationError(
                f"Violación de política de datos: La tarea con clasificación 'local_only' "
                f"no puede enviarse al proveedor remoto '{provider.provider_name}'."
            )

        # 2. Regla: restricted requiere aprobación explícita en metadata
        if classification == "restricted":
            human_approved = request.metadata.get("human_approved", False)
            if not human_approved and not provider.is_local:
                raise PolicyViolationError(
                    f"Violación de política de datos: El contexto 'restricted' requiere aprobación "
                    f"humana explícita antes de transmitirse a '{provider.provider_name}'."
                )

    @staticmethod
    def sanitize_log_payload(payload: dict[str, Any]) -> dict[str, Any]:
        """Elimina posibles secretos o tokens de los registros de auditoría."""
        sanitized = payload.copy()
        sensitive_keys = {"token", "key", "secret", "password", "authorization", "api_key"}
        for k, v in list(sanitized.items()):
            if any(s in k.lower() for s in sensitive_keys):
                sanitized[k] = "[REDACTED]"
            elif isinstance(v, dict):
                sanitized[k] = ModelPolicyEngine.sanitize_log_payload(v)
        return sanitized
