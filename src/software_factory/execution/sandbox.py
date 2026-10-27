"""Ejecutor de comandos con allowlist estricta, timeouts y cuotas de salida."""

import os
import sys
import shutil
import shlex
import time
import asyncio
from pathlib import Path
from pydantic import BaseModel


class CommandSecurityError(Exception):
    """Excepción lanzada cuando un comando viola la política de seguridad."""
    pass


class ExecutionResult(BaseModel):
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    is_timed_out: bool = False


# Catálogo de comandos binarios permitidos y sus subcomandos autorizados
ALLOWED_COMMANDS_SPEC: dict[str, set[str] | None] = {
    "git": {"status", "diff", "log", "branch", "worktree", "rev-parse", "add", "commit"},
    "pytest": None,  # Todos los argumentos de pytest son válidos
    "python": None,
    "python3": None,
    "ruff": {"check", "format"},
    "node": None,
    "npm": {"test", "run", "build", "ci", "list", "view"},
    "npx": {"playwright", "cap", "tsc", "eslint"},
    "cargo": {"test", "build", "check"},
}

DANGEROUS_CHARACTERS = {";", "&", "|", "`", "$", ">", "<", "\n", "\r"}


class CommandExecutor:
    """Ejecutor de procesos asíncronos en entornos controlados y worktrees."""

    def __init__(
        self,
        default_timeout: float = 60.0,
        max_output_bytes: int = 1048576,  # 1 MB
        allowed_spec: dict[str, set[str] | None] | None = None,
    ):
        self.default_timeout = default_timeout
        self.max_output_bytes = max_output_bytes
        self.allowed_spec = allowed_spec or ALLOWED_COMMANDS_SPEC

    def validate_command(self, cmd_input: str | list[str]) -> list[str]:
        """Valida que el comando no contenga inyecciones de shell y cumpla la allowlist."""
        if isinstance(cmd_input, str):
            # Detectar caracteres peligrosos de encadenamiento antes del parsing
            if any(char in cmd_input for char in DANGEROUS_CHARACTERS):
                raise CommandSecurityError(
                    f"Comando rechazado: contiene caracteres de encadenamiento o redirección no permitidos."
                )
            tokens = shlex.split(cmd_input)
        else:
            tokens = list(cmd_input)

        if not tokens:
            raise CommandSecurityError("Comando vacío rechazado.")

        base_bin = Path(tokens[0]).name

        if base_bin not in self.allowed_spec:
            raise CommandSecurityError(
                f"Ejecutable '{base_bin}' no está en la lista de comandos permitidos ({list(self.allowed_spec.keys())})."
            )

        allowed_subcommands = self.allowed_spec[base_bin]
        if allowed_subcommands is not None and len(tokens) > 1:
            # Buscar el primer subcomando no-flag
            subcmd = None
            for t in tokens[1:]:
                if not t.startswith("-"):
                    subcmd = t
                    break
            if subcmd and subcmd not in allowed_subcommands:
                raise CommandSecurityError(
                    f"Subcomando '{subcmd}' no permitido para '{base_bin}'. Permitidos: {allowed_subcommands}"
                )

        return tokens

    async def execute(
        self,
        command: str | list[str],
        cwd: Path | str | None = None,
        timeout: float | None = None,
    ) -> ExecutionResult:
        """Ejecuta el comando en modo subprocess seguro (sin shell=True)."""
        tokens = self.validate_command(command)
        run_timeout = timeout or self.default_timeout
        working_dir = str(cwd) if cwd else None

        # Inyectar el entorno virtual activo al inicio de PATH
        exec_env = os.environ.copy()
        venv_bin = Path(sys.executable).parent
        if venv_bin.exists():
            exec_env["PATH"] = f"{venv_bin}{os.pathsep}{exec_env.get('PATH', '')}"

        # Resolver ruta canónica del ejecutable en el PATH efectivo
        bin_resolved = shutil.which(tokens[0], path=exec_env.get("PATH"))
        cmd_tokens = [bin_resolved if bin_resolved else tokens[0]] + tokens[1:]

        start_time = time.perf_counter()
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd_tokens,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
                env=exec_env,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=run_timeout,
                )
                is_timed_out = False
                exit_code = process.returncode or 0
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                stdout_bytes, stderr_bytes = b"", b"Command timed out and was killed"
                is_timed_out = True
                exit_code = -1

            duration_ms = (time.perf_counter() - start_time) * 1000

            # Aplicar límite de tamaño de salida
            truncated_stdout = stdout_bytes[:self.max_output_bytes].decode("utf-8", errors="replace")
            truncated_stderr = stderr_bytes[:self.max_output_bytes].decode("utf-8", errors="replace")

            return ExecutionResult(
                command=tokens,
                exit_code=exit_code,
                stdout=truncated_stdout,
                stderr=truncated_stderr,
                duration_ms=round(duration_ms, 2),
                is_timed_out=is_timed_out,
            )

        except Exception as exc:
            duration_ms = (time.perf_counter() - start_time) * 1000
            return ExecutionResult(
                command=tokens,
                exit_code=-2,
                stdout="",
                stderr=f"Fallo de ejecución de proceso: {str(exc)}",
                duration_ms=round(duration_ms, 2),
                is_timed_out=False,
            )
