"""Módulo de perfiles declarativos de proyecto para la Software Factory."""

from software_factory.profiler.models import (
    ProjectArchetype,
    UIUXMode,
    ProjectProfile,
)
from software_factory.profiler.loader import (
    load_profile_from_file,
    load_profile_from_repo,
    auto_detect_profile,
    check_protected_paths,
)

__all__ = [
    "ProjectArchetype",
    "UIUXMode",
    "ProjectProfile",
    "load_profile_from_file",
    "load_profile_from_repo",
    "auto_detect_profile",
    "check_protected_paths",
]
