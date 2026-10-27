"""Pruebas para el ejecutor seguro (sandbox), detector de secretos y Git worktrees."""

import pytest
import asyncio
from pathlib import Path
from software_factory.execution.sandbox import CommandExecutor, CommandSecurityError
from software_factory.security.secret_scanner import SecretScanner
from software_factory.git.worktree import WorktreeManager


@pytest.mark.asyncio
async def test_command_executor_allowed_command():
    executor = CommandExecutor()
    res = await executor.execute(["git", "status"])
    assert res.exit_code == 0
    assert "On branch" in res.stdout or "fatal" not in res.stderr


def test_command_executor_validates_livestock_stack():
    executor = CommandExecutor()
    # Comandos autorizados para Livestock Manager
    assert executor.validate_command("npm test") == ["npm", "test"]
    assert executor.validate_command("npx playwright test") == ["npx", "playwright", "test"]
    assert executor.validate_command("cargo test") == ["cargo", "test"]
    assert executor.validate_command("node --version") == ["node", "--version"]

    # Subcomandos bloqueados fuera de la allowlist
    with pytest.raises(CommandSecurityError):
        executor.validate_command("npm install -g malicious-package")
    with pytest.raises(CommandSecurityError):
        executor.validate_command("cargo install eviltarget")


@pytest.mark.asyncio
async def test_command_executor_blocks_disallowed_binary():
    executor = CommandExecutor()
    with pytest.raises(CommandSecurityError) as exc_info:
        await executor.execute("curl https://example.com")
    assert "no está en la lista de comandos permitidos" in str(exc_info.value)


@pytest.mark.asyncio
async def test_command_executor_blocks_shell_chaining_and_pipes():
    executor = CommandExecutor()
    dangerous_inputs = [
        "git status; rm -rf /",
        "git status && pytest",
        "git status | grep master",
        "git log `whoami`",
        "git diff > output.txt",
    ]
    for cmd in dangerous_inputs:
        with pytest.raises(CommandSecurityError) as exc_info:
            await executor.execute(cmd)
        assert "caracteres de encadenamiento" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_command_executor_timeout_enforcement():
    executor = CommandExecutor(default_timeout=0.2)
    # python sleep mayor que el timeout
    res = await executor.execute(["python3", "-c", "import time; time.sleep(1.0)"])
    assert res.is_timed_out is True
    assert res.exit_code == -1
    assert "timed out" in res.stderr


def test_secret_scanner_detects_credentials():
    dirty_diff = """
    --- a/config.py
    +++ b/config.py
    @@ -1,3 +1,4 @@
    +OPENAI_KEY = "sk-1234567890abcdef1234567890abcdef1234"
    +GITHUB_PAT = "ghp_1234567890abcdefghijklmnopqrstuvwxyz12"
    +AWS_KEY = "AKIAIOSFODNN7EXAMPLE"
    +NORMAL_LINE = "Hola mundo"
    """
    findings = SecretScanner.scan_diff(dirty_diff)
    assert len(findings) == 3
    rules = [f.rule for f in findings]
    assert "Token de OpenAI" in rules
    assert "Token de GitHub" in rules
    assert "Clave AWS Access Key" in rules


def test_secret_scanner_passes_clean_diff():
    clean_diff = """
    --- a/math.py
    +++ b/math.py
    @@ -1,2 +1,3 @@
    +def add(a: int, b: int) -> int:
    +    return a + b
    """
    findings = SecretScanner.scan_diff(clean_diff)
    assert len(findings) == 0


@pytest.mark.asyncio
async def test_worktree_lifecycle_in_repo(tmp_path: Path):
    """Prueba el ciclo de vida de un worktree en el repositorio real de la fábrica."""
    manager = WorktreeManager()
    task_id = "TASK-TEST-WORKTREE"

    try:
        wt_path = await manager.create_worktree(task_id)
        assert wt_path.exists()
        assert (wt_path / ".git").exists()  # Los worktrees tienen un archivo .git

        # Verificar diff vacío inicialmente
        diff = await manager.get_diff(task_id)
        assert isinstance(diff, str)

        # Escanear secretos (debe ser 0)
        secrets = await manager.scan_diff_for_secrets(task_id)
        assert len(secrets) == 0

    finally:
        # Limpieza obligatoria
        await manager.remove_worktree(task_id)
        assert not manager.get_worktree_path(task_id).exists()
