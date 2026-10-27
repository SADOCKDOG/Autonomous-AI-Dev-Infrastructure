"""Gestor centralizado de políticas y directivas de rol para agentes (Policy Manager).
Alineado con ISO/IEC 42001 y Microsoft Responsible AI.
"""

import hashlib
from pathlib import Path
from typing import Dict, Tuple, Optional

# Directorio base de políticas
_ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
POLICIES_DIR = _ROOT_DIR / "policies"

# Mapeo de roles a archivos de política
ROLE_POLICY_MAP: Dict[str, str] = {
    "analyst": "policy_analyst.md",
    "architect": "policy_architect.md",
    "developer": "policy_developer.md",
    "uiux": "policy_uiux.md",
    "tester": "policy_tester.md",
    "reviewer": "policy_reviewer.md",
}

# Caché en memoria: role -> (content, sha256_hash)
_POLICY_CACHE: Dict[str, Tuple[str, str]] = {}


class PolicyManager:
    """Administrador de carga, verificación criptográfica y composición de directivas de agentes."""

    @classmethod
    def load_role_policy(cls, role: str) -> Tuple[str, str]:
        """Carga la directiva de rol oficial desde el archivo Markdown correspondiente.
        Retorna:
            Tuple[str, str]: (contenido_politica, sha256_hash)
        """
        if role in _POLICY_CACHE:
            return _POLICY_CACHE[role]

        policy_file = ROLE_POLICY_MAP.get(role)
        if not policy_file:
            # Fallback genérico para roles no catalogados
            content = f"# Directiva General para Agente '{role}'\nActúa con rigor de ingeniería y cumple los estándares del proyecto."
            sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
            _POLICY_CACHE[role] = (content, sha256)
            return content, sha256

        file_path = POLICIES_DIR / policy_file
        if not file_path.exists():
            content = f"# Directiva no encontrada para '{role}' en {file_path.name}\nOperar en modo de protección de código."
            sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
            return content, sha256

        content = file_path.read_text(encoding="utf-8")
        sha256 = hashlib.sha256(content.encode("utf-8")).hexdigest()
        _POLICY_CACHE[role] = (content, sha256)
        return content, sha256

    @classmethod
    def build_consolidated_prompt(
        cls,
        role: str,
        role_schema_prompt: Optional[str] = None,
        project_context: Optional[str] = None,
        design_tokens_context: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Construye el prompt de sistema consolidado en tres capas:
        Capa 1: Directiva de Rol obligatoria (SOP-SF-001)
        Capa 2: Contexto del Proyecto y Tokens de Diseño de la Plataforma
        Capa 3: Instrucciones específicas de esquema de salida JSON

        Retorna:
            Tuple[str, str]: (system_prompt_consolidado, policy_hash)
        """
        policy_content, policy_hash = cls.load_role_policy(role)

        sections = [
            "=== DIRECTIVA DE ROL DE OBLIGADO CUMPLIMIENTO (CAPA 1: GOBERNANZA ISO/IEC 42001) ===",
            policy_content.strip(),
        ]

        if project_context:
            sections.append("\n=== CONTEXTO DEL PROYECTO OBJETIVO (CAPA 2: ARQUITECTURA) ===")
            sections.append(project_context.strip())

        if design_tokens_context:
            sections.append("\n=== SISTEMA DE DISEÑO Y TOKENS AUTORIZADOS (CAPA 2: DESIGN TOKENS) ===")
            sections.append(design_tokens_context.strip())

        if role_schema_prompt:
            sections.append("\n=== INSTRUCCIONES OPERATIVAS Y ESQUEMA DE SALIDA (CAPA 3: PROTOCOLO JSON) ===")
            sections.append(role_schema_prompt.strip())

        consolidated = "\n\n".join(sections)
        return consolidated, policy_hash
