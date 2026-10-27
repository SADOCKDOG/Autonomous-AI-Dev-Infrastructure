"""Agente Diseñador UI/UX y Validador de Tokens (Fase 2 de Gobernanza Visual).
Alineado con directiva POL-ROLE-004 e ISO/IEC 42001.
"""

from enum import Enum
import re
from pathlib import Path
from pydantic import BaseModel, Field
from software_factory.agents.base import BaseAgent
from software_factory.profiler.models import ProjectProfile, ProjectArchetype, UIUXMode


class UIUXStatus(str, Enum):
    """Estados del veredicto del agente UI/UX."""
    APPROVED = "approved"
    APPROVED_WITH_WARNINGS = "approved_with_warnings"
    REJECTED = "rejected"
    SKIPPED = "skipped"


class UIUXVerdict(BaseModel):
    """Veredicto técnico y ergonómico emitido por el agente UI/UX."""
    status: UIUXStatus = UIUXStatus.APPROVED
    passed: bool = True
    archetype: str = "generic"
    uiux_mode: str = "advisory"
    findings: list[str] = Field(default_factory=list)
    tokens_detected: list[str] = Field(default_factory=list)
    inline_styles_count: int = 0
    raw_hex_colors_count: int = 0
    touch_target_warnings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    summary: str = ""


# Extensiones reconocidas de archivos de interfaz y presentación
UI_EXTENSIONS = {".html", ".htm", ".css", ".scss", ".jsx", ".tsx", ".vue", ".svelte"}

# Expresiones regulares para análisis estático determinista
RE_INLINE_STYLE = re.compile(r'style\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
RE_CSS_VAR = re.compile(r'var\((--[a-zA-Z0-9_-]+)\)')
RE_HEX_COLOR = re.compile(r'#[0-9a-fA-F]{3,8}\b')
RE_SMALL_TOUCH_TARGET = re.compile(r'(?:min-)?(?:width|height)\s*:\s*([1-3]?[0-9]|4[0-3])px', re.IGNORECASE)


class UIUXAgent(BaseAgent):
    """Agente auditor de diseño, ergonomía y conformidad de tokens visuales."""

    def __init__(self, gateway=None):
        super().__init__(role="uiux", gateway=gateway)

    async def evaluate_ui(
        self,
        task_id: str,
        worktree_path: Path,
        profile: ProjectProfile,
        changed_files: list[str],
        diff_text: str = "",
    ) -> UIUXVerdict:
        """Audita los cambios de interfaz de usuario conforme al perfil declarativo del proyecto."""
        # 1. Modo omitido por perfil
        if profile.uiux_mode == UIUXMode.NONE:
            return UIUXVerdict(
                status=UIUXStatus.SKIPPED,
                passed=True,
                archetype=profile.archetype.value,
                uiux_mode=profile.uiux_mode.value,
                summary="Gobernanza UI/UX omitida según configuración de perfil.",
            )

        # 2. Filtrar archivos relevantes de UI
        ui_files = [f for f in changed_files if Path(f).suffix.lower() in UI_EXTENSIONS]
        if not ui_files and not any(ext in diff_text for ext in [".css", ".html", "class=", "style="]):
            return UIUXVerdict(
                status=UIUXStatus.SKIPPED,
                passed=True,
                archetype=profile.archetype.value,
                uiux_mode=profile.uiux_mode.value,
                summary="No se detectaron modificaciones en archivos o plantillas de interfaz de usuario.",
            )

        findings: list[str] = []
        recommendations: list[str] = []
        tokens_detected: list[str] = []

        # 3. Análisis del diff y archivos UI en el worktree
        inline_matches = RE_INLINE_STYLE.findall(diff_text)
        var_matches = set(RE_CSS_VAR.findall(diff_text))
        hex_matches = RE_HEX_COLOR.findall(diff_text)
        touch_warnings: list[str] = []

        tokens_detected.extend(sorted(list(var_matches)))

        # Detección de estilos inline
        if inline_matches:
            findings.append(
                f"Se detectaron {len(inline_matches)} estilos inline en el diff. "
                "Se recomienda emplear clases CSS y tokens centralizados."
            )
            recommendations.append("Extraer estilos inline a hojas de estilo modulares o tokens oficiales.")

        # Detección de colores hexadecimales crudos sin token
        if hex_matches and len(hex_matches) > len(var_matches):
            findings.append(
                f"Se detectaron {len(hex_matches)} valores de color hexadecimales directos. "
                "Considere utilizar variables CSS (ej. var(--p-gold), var(--bg-card))."
            )
            recommendations.append("Vincular la paleta a las variables del Design System declarado.")

        # 4. Validaciones específicas por arquetipo arquitectónico
        if profile.archetype == ProjectArchetype.MOBILE_PWA:
            small_targets = RE_SMALL_TOUCH_TARGET.findall(diff_text)
            if small_targets:
                msg = (
                    f"Detección de dimensiones táctiles inferiores a 44-48px ({len(small_targets)} ocurrencias). "
                    "En arquetipo móvil, asegure objetivos táctiles ergonómicos de al menos 48x48 dp."
                )
                touch_warnings.append(msg)
                findings.append(msg)
                recommendations.append("Asegurar min-width / min-height de 48px en controles interactivos móviles.")

        elif profile.archetype == ProjectArchetype.DESKTOP_TAURI:
            if "erp" not in diff_text.lower() and "sidebar" not in diff_text.lower() and ui_files:
                recommendations.append("Verificar que la nueva vista se integre armónicamente en el Shell de ERP de escritorio.")

        # 5. Determinación del veredicto según modo (Advisory vs Strict)
        is_strict = (profile.uiux_mode == UIUXMode.STRICT)
        critical_violations = len(inline_matches) > 3 or (len(hex_matches) > 5 and not tokens_detected)

        if not findings and not touch_warnings:
            status = UIUXStatus.APPROVED
            passed = True
            summary = "Conformidad visual y de tokens de diseño aprobada sin observaciones."
        elif is_strict and critical_violations:
            status = UIUXStatus.REJECTED
            passed = False
            summary = f"Auditoría UI/UX rechazada en modo estricto: {len(findings)} violaciones críticas detectadas."
        else:
            status = UIUXStatus.APPROVED_WITH_WARNINGS
            passed = True
            summary = (
                f"Evaluación UI/UX completada con advertencias ({len(findings)} observaciones). "
                f"Modo asesor activo: no bloquea el flujo técnico."
            )

        return UIUXVerdict(
            status=status,
            passed=passed,
            archetype=profile.archetype.value,
            uiux_mode=profile.uiux_mode.value,
            findings=findings,
            tokens_detected=tokens_detected,
            inline_styles_count=len(inline_matches),
            raw_hex_colors_count=len(hex_matches),
            touch_target_warnings=touch_warnings,
            recommendations=recommendations,
            summary=summary,
        )
