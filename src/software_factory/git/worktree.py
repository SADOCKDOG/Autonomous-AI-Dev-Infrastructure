"""Gestor de aislamiento de tareas mediante Git Worktrees."""

import os
import shutil
from pathlib import Path
from software_factory.settings import settings
from software_factory.execution.sandbox import CommandExecutor, CommandSecurityError
from software_factory.security.secret_scanner import SecretScanner, SecretFinding


class WorktreeError(Exception):
    """Excepción de fallo en operaciones de Git Worktree."""
    pass


class WorktreeManager:
    """Gestiona la creación, aislamiento, diff y limpieza de Git worktrees por tarea."""

    def __init__(self, repo_dir: Path | None = None, worktrees_dir: Path | None = None):
        self.repo_dir = repo_dir or settings.base_dir
        self.worktrees_dir = worktrees_dir or (self.repo_dir / ".worktrees")
        self.executor = CommandExecutor()

    def get_worktree_path(self, task_id: str) -> Path:
        clean_id = task_id.lower().replace(":", "-")
        return self.worktrees_dir / clean_id

    def get_branch_name(self, task_id: str) -> str:
        clean_id = task_id.lower().replace(":", "-")
        return f"feat/{clean_id}"

    async def create_worktree(self, task_id: str, base_branch: str = "master") -> Path:
        """Crea una rama y un directorio de worktree aislado para la tarea."""
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)
        worktree_path = self.get_worktree_path(task_id)
        branch_name = self.get_branch_name(task_id)

        if worktree_path.exists():
            return worktree_path

        # Intentar crear rama y worktree
        cmd = ["git", "worktree", "add", "-b", branch_name, str(worktree_path), base_branch]
        res = await self.executor.execute(cmd, cwd=self.repo_dir)

        if res.exit_code != 0:
            # Si la rama ya existe, adjuntar el worktree a la rama existente
            cmd_existing = ["git", "worktree", "add", str(worktree_path), branch_name]
            res2 = await self.executor.execute(cmd_existing, cwd=self.repo_dir)
            if res2.exit_code != 0:
                raise WorktreeError(f"Error creando worktree para {task_id}: {res2.stderr or res.stderr}")

        return worktree_path

    async def get_diff(self, task_id: str, base_branch: str = "master") -> str:
        """Obtiene el diff acumulado del worktree frente a la rama base."""
        worktree_path = self.get_worktree_path(task_id)
        if not worktree_path.exists():
            return ""

        res = await self.executor.execute(["git", "diff", f"{base_branch}...HEAD"], cwd=worktree_path)
        if res.exit_code != 0:
            # Si aún no hay commits, mostrar diff del working directory
            res = await self.executor.execute(["git", "diff"], cwd=worktree_path)
        return res.stdout

    async def scan_diff_for_secrets(self, task_id: str, base_branch: str = "master") -> list[SecretFinding]:
        """Escanea el diff de la tarea buscando cualquier credencial antes de revisión."""
        diff_text = await self.get_diff(task_id, base_branch=base_branch)
        return SecretScanner.scan_diff(diff_text)

    async def remove_worktree(self, task_id: str) -> None:
        """Desmonta y elimina de forma segura el worktree asociado a la tarea."""
        worktree_path = self.get_worktree_path(task_id)
        if not worktree_path.exists():
            return

        cmd = ["git", "worktree", "remove", "--force", str(worktree_path)]
        await self.executor.execute(cmd, cwd=self.repo_dir)
        await self.executor.execute(["git", "worktree", "prune"], cwd=self.repo_dir)

        if worktree_path.exists():
            shutil.rmtree(worktree_path, ignore_errors=True)
