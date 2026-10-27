"""Pruebas unitarias para el Sistema de Perfiles Declarativos de Proyecto."""

import json
from pathlib import Path
import pytest
from software_factory.profiler.models import (
    ProjectProfile,
    ProjectArchetype,
    UIUXMode,
)
from software_factory.profiler.loader import (
    load_profile_from_file,
    load_profile_from_repo,
    auto_detect_profile,
    check_protected_paths,
)
from software_factory.agents.tester import TesterAgent
from software_factory.execution.sandbox import CommandExecutor, ExecutionResult


def test_project_profile_defaults_and_normalization():
    """Valida valores por defecto y normalización de comandos desde cadena a lista."""
    profile = ProjectProfile(
        project_name="my-service",
        test_command="npm run test:ci",
        lint_command="ruff check .",
    )
    assert profile.archetype == ProjectArchetype.GENERIC
    assert profile.uiux_mode == UIUXMode.ADVISORY
    assert profile.test_command == ["npm", "run", "test:ci"]
    assert profile.lint_command == ["ruff", "check", "."]
    assert profile.build_command is None


def test_load_profile_from_file(tmp_path: Path):
    """Verifica la carga deserializada desde un archivo .factory/config.json."""
    cfg_dir = tmp_path / ".factory"
    cfg_dir.mkdir(parents=True)
    cfg_file = cfg_dir / "config.json"

    data = {
        "project_name": "livestock-desktop",
        "archetype": "desktop_tauri",
        "base_branch": "master",
        "test_command": ["cargo", "test"],
        "uiux_mode": "strict",
        "design_tokens_path": "frontend/css/erp-sidebar.css",
        "protected_paths": ["android/**", "ios/**"],
    }
    cfg_file.write_text(json.dumps(data), encoding="utf-8")

    profile = load_profile_from_file(cfg_file)
    assert profile.project_name == "livestock-desktop"
    assert profile.archetype == ProjectArchetype.DESKTOP_TAURI
    assert profile.uiux_mode == UIUXMode.STRICT
    assert profile.test_command == ["cargo", "test"]
    assert profile.protected_paths == ["android/**", "ios/**"]


def test_auto_detect_desktop_tauri(tmp_path: Path):
    """Detecta automáticamente un proyecto de escritorio Tauri si existe src-tauri/."""
    tauri_dir = tmp_path / "src-tauri"
    tauri_dir.mkdir()
    (tauri_dir / "tauri.conf.json").write_text("{}", encoding="utf-8")

    profile = load_profile_from_repo(tmp_path)
    assert profile.archetype == ProjectArchetype.DESKTOP_TAURI
    assert "android/**" in profile.protected_paths
    assert profile.test_command == ["npm", "test"]


def test_auto_detect_mobile_pwa_maestro_android(tmp_path: Path):
    """Detecta automáticamente la app MAESTRO ANDROID por presencia de android/ y custom runner."""
    (tmp_path / "android").mkdir()
    unit_dir = tmp_path / "tests" / "unit"
    unit_dir.mkdir(parents=True)
    (unit_dir / "run_all.js").write_text("// test runner", encoding="utf-8")

    profile = load_profile_from_repo(tmp_path)
    assert profile.archetype == ProjectArchetype.MOBILE_PWA
    assert profile.test_command == ["node", "tests/unit/run_all.js"]
    assert "src-tauri/**" in profile.protected_paths


def test_auto_detect_python_service(tmp_path: Path):
    """Detecta automáticamente un microservicio o librería Python por pyproject.toml."""
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'", encoding="utf-8")

    profile = load_profile_from_repo(tmp_path)
    assert profile.archetype == ProjectArchetype.PYTHON_SERVICE
    assert profile.test_command == ["pytest", "-q"]
    assert profile.base_branch == "main"


def test_check_protected_paths_detects_violations():
    """Verifica que el matcher identifique violaciones de arquitectura en ramas."""
    profile = ProjectProfile(
        project_name="desktop-app",
        archetype=ProjectArchetype.DESKTOP_TAURI,
        protected_paths=["android/**", "capacitor.config.*"],
    )

    changed_files = [
        "frontend/js/app.js",
        "frontend/css/style.css",
        "android/app/build.gradle",
        "capacitor.config.ts",
    ]

    violations = check_protected_paths(profile, changed_files)
    assert len(violations) == 2
    assert "android/app/build.gradle" in violations
    assert "capacitor.config.ts" in violations


@pytest.mark.asyncio
async def test_tester_agent_honors_declarative_profile(tmp_path: Path, monkeypatch):
    """Verifica que el TesterAgent ejecute el comando definido en el perfil declarativo."""
    class MockExecutor:
        def __init__(self):
            self.executed_cmd = None

        async def execute(self, cmd, cwd, **kwargs):
            self.executed_cmd = cmd
            return ExecutionResult(
                command=cmd,
                exit_code=0,
                stdout="16 tests passed",
                stderr="",
                duration_ms=120.0,
            )

    mock_exec = MockExecutor()
    agent = TesterAgent(executor=mock_exec)

    custom_profile = ProjectProfile(
        project_name="MAESTRO-ANDROID",
        archetype=ProjectArchetype.MOBILE_PWA,
        test_command=["node", "tests/unit/run_all.js"],
    )

    verdict = await agent.run_tests("TASK-PROFILER-01", tmp_path, profile=custom_profile)

    assert verdict.tests_passed is True
    assert mock_exec.executed_cmd == ["node", "tests/unit/run_all.js"]
    assert "node tests/unit/run_all.js" in verdict.summary


def test_actual_repository_profiles_if_present():
    """Valida los perfiles reales desplegados en los repositorios locales si existen."""
    repos_base = Path(__file__).resolve().parent.parent.parent.parent

    # 1. Repositorio de la propia factoría
    dev_profile = load_profile_from_repo(Path(__file__).resolve().parent.parent.parent)
    assert dev_profile.project_name == "AutonomousDev"
    assert dev_profile.archetype == ProjectArchetype.PYTHON_SERVICE
    assert dev_profile.test_command == ["pytest", "-q"]

    # 2. LIVESTOCK-MANAGER (MAESTRO ANDROID)
    maestro_dir = repos_base / "LIVESTOCK-MANAGER"
    if maestro_dir.exists():
        maestro_profile = load_profile_from_repo(maestro_dir)
        assert maestro_profile.project_name == "LIVESTOCK-MANAGER"
        assert maestro_profile.archetype == ProjectArchetype.MOBILE_PWA
        assert maestro_profile.test_command == ["node", "tests/porcine-traceability.unit.test.js"]
        assert "src-tauri/**" in maestro_profile.protected_paths

    # 3. livestock-desktop
    desktop_dir = repos_base / "livestock-desktop"
    if desktop_dir.exists():
        desktop_profile = load_profile_from_repo(desktop_dir)
        assert desktop_profile.project_name == "livestock-desktop"
        assert desktop_profile.archetype == ProjectArchetype.DESKTOP_TAURI
        assert "android/**" in desktop_profile.protected_paths

