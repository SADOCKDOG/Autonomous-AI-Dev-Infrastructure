"""Pruebas unitarias para el Agente UI/UX y la gobernanza visual (Fase 2)."""

from pathlib import Path
import pytest
from software_factory.agents.uiux import UIUXAgent, UIUXStatus, UIUXVerdict
from software_factory.profiler.models import ProjectProfile, ProjectArchetype, UIUXMode


@pytest.mark.asyncio
async def test_uiux_agent_skips_when_mode_is_none():
    """Verifica que el agente UI/UX no evalúe si el perfil tiene uiux_mode=NONE."""
    agent = UIUXAgent()
    profile = ProjectProfile(
        project_name="backend-service",
        archetype=ProjectArchetype.PYTHON_SERVICE,
        uiux_mode=UIUXMode.NONE,
    )
    verdict = await agent.evaluate_ui(
        task_id="TASK-UI-01",
        worktree_path=Path("/tmp/mock"),
        profile=profile,
        changed_files=["templates/index.html"],
        diff_text="+<div style='color: red;'>Hola</div>",
    )
    assert verdict.status == UIUXStatus.SKIPPED
    assert verdict.passed is True
    assert "omitida" in verdict.summary


@pytest.mark.asyncio
async def test_uiux_agent_skips_when_no_ui_files_changed():
    """Verifica que el agente UI/UX se omita si los archivos modificados son solo backend/scripts."""
    agent = UIUXAgent()
    profile = ProjectProfile(
        project_name="livestock-core",
        archetype=ProjectArchetype.MOBILE_PWA,
        uiux_mode=UIUXMode.ADVISORY,
    )
    verdict = await agent.evaluate_ui(
        task_id="TASK-UI-02",
        worktree_path=Path("/tmp/mock"),
        profile=profile,
        changed_files=["src/server/database.py", "scripts/migrate.sql"],
        diff_text="+def execute_query(): pass",
    )
    assert verdict.status == UIUXStatus.SKIPPED
    assert verdict.passed is True


@pytest.mark.asyncio
async def test_uiux_agent_advisory_mode_emits_warnings_without_blocking():
    """Verifica que en modo ADVISORY las advertencias de estilos inline no bloqueen el flujo."""
    agent = UIUXAgent()
    profile = ProjectProfile(
        project_name="MAESTRO-ANDROID",
        archetype=ProjectArchetype.MOBILE_PWA,
        uiux_mode=UIUXMode.ADVISORY,
    )
    diff = """
    +<button style="background: #ff5500; font-size: 14px;">Confirmar</button>
    """
    verdict = await agent.evaluate_ui(
        task_id="TASK-UI-03",
        worktree_path=Path("/tmp/mock"),
        profile=profile,
        changed_files=["index.html"],
        diff_text=diff,
    )
    assert verdict.status == UIUXStatus.APPROVED_WITH_WARNINGS
    assert verdict.passed is True
    assert verdict.inline_styles_count >= 1
    assert len(verdict.findings) >= 1
    assert "Modo asesor activo" in verdict.summary


@pytest.mark.asyncio
async def test_uiux_agent_strict_mode_rejects_critical_transgressions():
    """Verifica que en modo STRICT las transgresiones críticas de estilos causen rechazo (passed=False)."""
    agent = UIUXAgent()
    profile = ProjectProfile(
        project_name="livestock-desktop",
        archetype=ProjectArchetype.DESKTOP_TAURI,
        uiux_mode=UIUXMode.STRICT,
    )
    diff = """
    +<div style="color: #ff0000;">
    +  <span style="background: #00ff00;">Texto 1</span>
    +  <p style="margin: 10px; padding: 5px;">Texto 2</p>
    +  <b style="font-weight: bold;">Texto 3</b>
    +</div>
    """
    verdict = await agent.evaluate_ui(
        task_id="TASK-UI-04",
        worktree_path=Path("/tmp/mock"),
        profile=profile,
        changed_files=["frontend/index.html"],
        diff_text=diff,
    )
    assert verdict.status == UIUXStatus.REJECTED
    assert verdict.passed is False
    assert "rechazada en modo estricto" in verdict.summary


@pytest.mark.asyncio
async def test_uiux_agent_mobile_touch_target_ergonomics():
    """Verifica la detección de objetivos táctiles inferiores a 44-48px en arquetipo móvil."""
    agent = UIUXAgent()
    profile = ProjectProfile(
        project_name="MAESTRO-ANDROID",
        archetype=ProjectArchetype.MOBILE_PWA,
        uiux_mode=UIUXMode.ADVISORY,
    )
    diff = """
    +.btn-mini {
    +  width: 30px;
    +  height: 24px;
    +}
    """
    verdict = await agent.evaluate_ui(
        task_id="TASK-UI-05",
        worktree_path=Path("/tmp/mock"),
        profile=profile,
        changed_files=["css/components.css"],
        diff_text=diff,
    )
    assert len(verdict.touch_target_warnings) > 0
    assert "48x48" in verdict.touch_target_warnings[0]


@pytest.mark.asyncio
async def test_uiux_agent_approved_with_clean_tokens():
    """Verifica aprobación limpia cuando se emplean variables de diseño oficiales."""
    agent = UIUXAgent()
    profile = ProjectProfile(
        project_name="livestock-desktop",
        archetype=ProjectArchetype.DESKTOP_TAURI,
        uiux_mode=UIUXMode.STRICT,
    )
    diff = """
    +.erp-table-header {
    +  background-color: var(--bg-card);
    +  color: var(--p-gold);
    +  border-bottom: 1px solid var(--border-subtle);
    +}
    """
    verdict = await agent.evaluate_ui(
        task_id="TASK-UI-06",
        worktree_path=Path("/tmp/mock"),
        profile=profile,
        changed_files=["frontend/css/custom.css"],
        diff_text=diff,
    )
    assert verdict.status == UIUXStatus.APPROVED
    assert verdict.passed is True
    assert "--p-gold" in verdict.tokens_detected
    assert "--bg-card" in verdict.tokens_detected
    assert len(verdict.findings) == 0
