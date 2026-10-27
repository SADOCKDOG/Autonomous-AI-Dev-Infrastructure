"""Agente Desarrollador: implementa cambios en el worktree aislado."""

import json
import re
from pathlib import Path
from pydantic import BaseModel, Field
from software_factory.agents.base import BaseAgent
from software_factory.execution.sandbox import CommandExecutor
from software_factory.model_gateway.base import ChatMessage


class FileChange(BaseModel):
    path: str
    content: str


class DeveloperResult(BaseModel):
    commit_message: str
    files_modified: list[str] = Field(default_factory=list)
    files: list[FileChange] = Field(default_factory=list)
    implementation_notes: str = ""


DEVELOPER_SCHEMA_PROMPT = """Responde en formato JSON estricto con la siguiente estructura:
{
  "commit_message": "feat(modulo): descripcion concisa del cambio",
  "files": [
    {
      "path": "ruta/al/archivo.ext",
      "content": "contenido íntegro del archivo a crear o modificar"
    }
  ],
  "files_modified": ["ruta/al/archivo.ext"],
  "implementation_notes": "Detalles técnicos de la solución implementada"
}"""


class DeveloperAgent(BaseAgent):
    def __init__(self, gateway=None):
        super().__init__(role="developer", gateway=gateway)

    async def develop_task(
        self,
        task_id: str,
        title: str,
        plan_summary: str,
        plan_steps: list[str],
        worktree_path: Path,
        acceptance_criteria: list[str] | None = None,
        affected_files: list[str] | None = None,
        data_classification: str = "approved_code_context",
        project_context: str | None = None,
        design_tokens_context: str | None = None,
    ) -> DeveloperResult:
        steps_str = "\n".join(f"- {s}" for s in plan_steps)
        criteria_str = "\n".join(f"- {c}" for c in (acceptance_criteria or []))

        existing_context_blocks = []
        if affected_files:
            for rel in affected_files:
                target_f = (worktree_path / rel).resolve()
                if target_f.exists() and target_f.is_file():
                    try:
                        text = target_f.read_text(encoding="utf-8", errors="ignore")
                        snippet = text if len(text) <= 12000 else text[:12000] + "\n... [truncado]"
                        existing_context_blocks.append(
                            f"--- INICIO ARCHIVO PREEXISTENTE: {rel} ---\n{snippet}\n--- FIN ARCHIVO PREEXISTENTE ---"
                        )
                    except Exception:
                        pass

        existing_prompt = ""
        if existing_context_blocks:
            existing_prompt = (
                "\n\nARCHIVOS PREEXISTENTES A MODIFICAR (PRESERVACIÓN OBLIGATORIA):\n"
                "REGLA DE ORO DE NO-REGRESIÓN: Debes PRESERVAR intacto el código, métodos y pruebas preexistentes. "
                "Agrega la nueva funcionalidad o nuevas aserciones sin borrar ni reescribir desde cero los archivos, "
                "respetando el sistema de módulos original (CommonJS con require/assert, UMD, etc.).\n\n"
                + "\n\n".join(existing_context_blocks)
            )

        user_prompt = (
            f"ID de Tarea: {task_id}\n"
            f"Título: {title}\n\n"
            f"Criterios de Aceptación a satisfacer:\n{criteria_str or '(No especificados)'}\n\n"
            f"Plan Arquitectónico: {plan_summary}\n"
            f"Pasos del Plan:\n{steps_str}\n"
            f"Worktree Path: {worktree_path}\n"
            f"{existing_prompt}\n\n"
            f"Implementa la solución completa generando en la clave 'files' cada uno de los archivos requeridos "
            f"(código fuente, pruebas o informes según los criterios). Responde en formato JSON estricto."
        )

        system_prompt, _ = self.get_consolidated_system_prompt(
            role_schema_prompt=DEVELOPER_SCHEMA_PROMPT,
            project_context=project_context,
            design_tokens_context=design_tokens_context,
        )

        messages = [
            ChatMessage(role="system", content=system_prompt),
            ChatMessage(role="user", content=user_prompt),
        ]

        response = await self.invoke_model(
            messages=messages,
            task_id=task_id,
            data_classification=data_classification,
            temperature=0.2,
        )

        result = self._parse_response(response.content, task_id, title)

        # Aplicar archivos generados en el worktree aislado de forma segura
        written_files: list[str] = []
        normalized_worktree = worktree_path.resolve()

        for file_entry in result.files:
            rel_path = file_entry.path.lstrip("/\\")
            target_path = (normalized_worktree / rel_path).resolve()
            # Validación estricta para impedir Directory Traversal fuera del worktree
            try:
                target_path.relative_to(normalized_worktree)
            except ValueError:
                continue

            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(file_entry.content, encoding="utf-8")
            written_files.append(rel_path)

        if written_files:
            result.files_modified = written_files
            executor = CommandExecutor()
            await executor.execute(["git", "add", "."], cwd=worktree_path)
            clean_msg = result.commit_message.replace("\n", " ").strip() or f"feat({task_id.lower()}): implementacion segun plan"
            await executor.execute(["git", "commit", "-m", clean_msg], cwd=worktree_path)

        return result

    def _parse_response(self, content: str, task_id: str, default_title: str) -> DeveloperResult:
        cleaned = content.strip()
        
        # 1. Intentar extraer de bloque de código markdown ```json ... ```
        raw_json = cleaned
        fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned)
        if fence_match:
            candidate = fence_match.group(1).strip()
            if candidate.startswith("{") and candidate.endswith("}"):
                raw_json = candidate

        # 2. Si aún no empieza/termina con {}, buscar el primer { y el último }
        if not (raw_json.startswith("{") and raw_json.endswith("}")):
            first_brace = cleaned.find("{")
            last_brace = cleaned.rfind("}")
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                raw_json = cleaned[first_brace:last_brace + 1]

        try:
            data = json.loads(raw_json, strict=False)
            files_raw = data.get("files", [])
            parsed_files: list[FileChange] = []
            for f in files_raw:
                if isinstance(f, dict) and "path" in f and "content" in f:
                    parsed_files.append(FileChange(path=str(f["path"]), content=str(f["content"])))

            return DeveloperResult(
                commit_message=data.get("commit_message", f"feat({task_id.lower()}): {default_title.lower()}"),
                files_modified=data.get("files_modified", [f.path for f in parsed_files]),
                files=parsed_files,
                implementation_notes=data.get("implementation_notes", ""),
            )
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Fallo al parsear JSON del desarrollador: %s", exc)
            return DeveloperResult(
                commit_message=f"feat({task_id.lower()}): {default_title.lower()}",
                files_modified=[],
                files=[],
                implementation_notes=f"Implementación completada según plan (parseo no estructurado: {exc}).",
            )
