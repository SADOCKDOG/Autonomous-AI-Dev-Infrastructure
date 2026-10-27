"""Pruebas unitarias para el PolicyManager y la carga de directivas normativas."""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from software_factory.agents.policy_manager import PolicyManager, POLICIES_DIR, ROLE_POLICY_MAP
from software_factory.agents.analyst import AnalystAgent
from software_factory.agents.architect import ArchitectAgent
from software_factory.agents.developer import DeveloperAgent
from software_factory.agents.reviewer import ReviewerAgent


def test_policies_directory_exists():
    assert POLICIES_DIR.exists(), f"El directorio {POLICIES_DIR} debe existir."
    for role, filename in ROLE_POLICY_MAP.items():
        policy_file = POLICIES_DIR / filename
        assert policy_file.exists(), f"El archivo de directiva {filename} para {role} debe existir."


def test_load_role_policy():
    content, sha256 = PolicyManager.load_role_policy("analyst")
    assert "Agente Analista" in content
    assert len(sha256) == 64
    assert isinstance(sha256, str)


def test_build_consolidated_prompt():
    prompt, policy_hash = PolicyManager.build_consolidated_prompt(
        role="developer",
        role_schema_prompt='{"commit_message": "..."}',
        project_context="Proyecto: LIVESTOCK-MANAGER",
        design_tokens_context="Tokens: var(--c-primary)",
    )
    assert "GOBERNANZA ISO/IEC 42001" in prompt
    assert "LIVESTOCK-MANAGER" in prompt
    assert "var(--c-primary)" in prompt
    assert '{"commit_message": "..."}' in prompt
    assert len(policy_hash) == 64


def test_agents_policy_property():
    analyst = AnalystAgent()
    assert analyst.policy_info is not None
    assert "Agente Analista" in analyst.policy_info[0]

    architect = ArchitectAgent()
    assert architect.policy_info is not None
    assert "Agente Arquitecto" in architect.policy_info[0]

    dev = DeveloperAgent()
    assert dev.policy_info is not None
    assert "Agente Desarrollador" in dev.policy_info[0]

    rev = ReviewerAgent()
    assert rev.policy_info is not None
    assert "Agente Revisor" in rev.policy_info[0]


def test_knowledge_base_source_of_truth():
    docs = PolicyManager.load_project_knowledge("livestock-manager")
    assert len(docs) >= 3
    assert "arquitectura-del-sistema" in docs

    summary = PolicyManager.get_project_knowledge_summary("livestock-manager")
    assert "FUENTE DE VERDAD DEL PROYECTO" in summary
    assert "LIVESTOCK-MANAGER" in summary

    # Probar resolución automática en build_consolidated_prompt pasando project_key
    prompt, _ = PolicyManager.build_consolidated_prompt(
        role="architect",
        project_key="livestock-manager",
    )
    assert "FUENTE DE VERDAD DEL PROYECTO" in prompt
    assert "ARQUITECTURA OFICIAL" in prompt


if __name__ == "__main__":
    print("Ejecutando pruebas de PolicyManager...")
    test_policies_directory_exists()
    print("1. test_policies_directory_exists: PASSED")
    test_load_role_policy()
    print("2. test_load_role_policy: PASSED")
    test_build_consolidated_prompt()
    print("3. test_build_consolidated_prompt: PASSED")
    test_agents_policy_property()
    print("4. test_agents_policy_property: PASSED")
    test_knowledge_base_source_of_truth()
    print("5. test_knowledge_base_source_of_truth: PASSED")
    print("Todas las pruebas de PolicyManager pasaron exitosamente.")
