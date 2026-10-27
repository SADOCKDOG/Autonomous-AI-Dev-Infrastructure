"""Cargador y detector automático de perfiles declarativos de proyecto."""

import json
import fnmatch
from pathlib import Path
from software_factory.profiler.models import (
    ProjectProfile,
    ProjectArchetype,
    UIUXMode,
)


def load_profile_from_file(config_path: Path) -> ProjectProfile:
    """Carga y valida un archivo de configuración de perfil (.json)."""
    if not config_path.exists() or not config_path.is_file():
        raise FileNotFoundError(f"Archivo de perfil no encontrado: {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    return ProjectProfile.model_validate(data)


def auto_detect_profile(repo_dir: Path) -> ProjectProfile:
    """Detecta de forma heurística el arquetipo y comandos de prueba para un repositorio."""
    project_name = repo_dir.name if repo_dir.name else "unnamed-project"

    # 1. Escritorio Tauri
    if (repo_dir / "src-tauri").is_dir() or (repo_dir / "src-tauri" / "tauri.conf.json").exists():
        return ProjectProfile(
            project_name=project_name,
            archetype=ProjectArchetype.DESKTOP_TAURI,
            base_branch="master",
            test_command=["npm", "test"],
            uiux_mode=UIUXMode.ADVISORY,
            design_tokens_path="frontend/css/erp-sidebar.css",
            protected_paths=["android/**", "ios/**", "capacitor.config.*"],
        )

    # 2. Móvil PWA (Maestro Android / Capacitor)
    if (
        (repo_dir / "android").is_dir()
        or (repo_dir / "capacitor.config.ts").exists()
        or (repo_dir / "capacitor.config.json").exists()
    ):
        has_porcine = (repo_dir / "tests" / "porcine-traceability.unit.test.js").exists()
        has_custom_runner = (repo_dir / "tests" / "unit" / "run_all.js").exists()
        if has_porcine:
            test_cmd = ["node", "tests/porcine-traceability.unit.test.js"]
        elif has_custom_runner:
            test_cmd = ["node", "tests/unit/run_all.js"]
        else:
            test_cmd = ["npm", "test"]
        return ProjectProfile(
            project_name=project_name,
            archetype=ProjectArchetype.MOBILE_PWA,
            base_branch="master",
            test_command=test_cmd,
            uiux_mode=UIUXMode.ADVISORY,
            design_tokens_path="css/theme.css",
            protected_paths=["src-tauri/**"],
        )

    # 3. Servicio o librería Python
    if (
        (repo_dir / "pyproject.toml").exists()
        or (repo_dir / "pytest.ini").exists()
        or (repo_dir / "setup.py").exists()
    ):
        return ProjectProfile(
            project_name=project_name,
            archetype=ProjectArchetype.PYTHON_SERVICE,
            base_branch="main",
            test_command=["pytest", "-q"],
            uiux_mode=UIUXMode.NONE,
        )

    # 4. Web SPA genérica
    if (repo_dir / "package.json").exists():
        return ProjectProfile(
            project_name=project_name,
            archetype=ProjectArchetype.WEB_SPA,
            base_branch="master",
            test_command=["npm", "test"],
            uiux_mode=UIUXMode.ADVISORY,
        )

    # 5. Fallback genérico
    return ProjectProfile(
        project_name=project_name,
        archetype=ProjectArchetype.GENERIC,
        base_branch="master",
        test_command=["git", "status"],
        uiux_mode=UIUXMode.NONE,
    )


def load_profile_from_repo(repo_dir: Path) -> ProjectProfile:
    """Resuelve la configuración declarativa del repositorio o infiere su perfil si no existe."""
    # Candidato 1: .factory/config.json
    dot_factory = repo_dir / ".factory" / "config.json"
    if dot_factory.exists():
        return load_profile_from_file(dot_factory)

    # Candidato 2: .factory.json en raíz
    root_factory = repo_dir / ".factory.json"
    if root_factory.exists():
        return load_profile_from_file(root_factory)

    # Inferencia automática
    return auto_detect_profile(repo_dir)


def check_protected_paths(profile: ProjectProfile, changed_files: list[str]) -> list[str]:
    """Comprueba si alguna ruta modificada infringe las restricciones de archivos protegidos.
    
    Retorna:
        list[str]: Lista de archivos que colisionan con patrones protegidos.
    """
    violations: list[str] = []
    if not profile.protected_paths:
        return violations

    for file_path in changed_files:
        norm_path = file_path.replace("\\", "/")
        for pattern in profile.protected_paths:
            norm_pattern = pattern.replace("\\", "/")
            if fnmatch.fnmatch(norm_path, norm_pattern):
                violations.append(file_path)
                break

    return violations


def resolve_repo_path(target_repo: str | None = None) -> Path:
    """Resuelve la ruta absoluta del repositorio objetivo, admitiendo nombres de repos hermanos o rutas absolutas."""
    from software_factory.settings import settings
    if not target_repo or str(target_repo).strip() in ("", "AutonomousDev", "self", "local"):
        return settings.base_dir

    p = Path(target_repo)
    if p.is_absolute() and p.exists():
        return p

    # Búsqueda en directorio de repositorios hermano (ej: C:\Users\yo\repo\LIVESTOCK-MANAGER)
    sibling = settings.base_dir.parent / target_repo
    if sibling.exists():
        return sibling

    # Búsqueda como subdirectorio
    subdir = settings.base_dir / target_repo
    if subdir.exists():
        return subdir

    return settings.base_dir
