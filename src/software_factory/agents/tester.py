"""Agente QA / Tester: ejecuta pruebas y valida resultados reproducibles."""

from pathlib import Path
from pydantic import BaseModel
from software_factory.agents.base import BaseAgent
from software_factory.execution.sandbox import CommandExecutor, ExecutionResult
from software_factory.profiler.models import ProjectProfile
from software_factory.profiler.loader import load_profile_from_repo


class TestVerdict(BaseModel):
    __test__ = False
    tests_passed: bool
    exit_code: int
    summary: str
    duration_ms: float
    stdout: str
    stderr: str


class TesterAgent(BaseAgent):
    __test__ = False
    def __init__(self, gateway=None, executor: CommandExecutor | None = None):
        super().__init__(role="tester", gateway=gateway)
        self.executor = executor or CommandExecutor(default_timeout=60.0)

    async def run_tests(
        self,
        task_id: str,
        worktree_path: Path,
        profile: ProjectProfile | None = None,
    ) -> TestVerdict:
        """Ejecuta la suite de pruebas mediante el sandbox seguro en el worktree según el perfil."""
        if profile is None:
            profile = load_profile_from_repo(worktree_path)

        cmd = profile.test_command
        res: ExecutionResult = await self.executor.execute(
            cmd,
            cwd=worktree_path,
        )

        passed = (res.exit_code == 0)
        summary = (
            f"Todas las pruebas pasaron satisfactoriamente ({' '.join(cmd)})."
            if passed
            else f"Fallo en pruebas con '{' '.join(cmd)}' (código {res.exit_code})."
        )

        return TestVerdict(
            tests_passed=passed,
            exit_code=res.exit_code,
            summary=summary,
            duration_ms=res.duration_ms,
            stdout=res.stdout,
            stderr=res.stderr,
        )
