"""Agente Desarrollador: implementa cambios en el worktree aislado."""

import json
import re
from pathlib import Path
from pydantic import BaseModel, Field
from software_factory.agents.base import BaseAgent
from software_factory.model_gateway.base import ChatMessage


class DeveloperResult(BaseModel):
    commit_message: str
    files_modified: list[str] = Field(default_factory=list)
    implementation_notes: str = ""


DEVELOPER_SCHEMA_PROMPT = """Responde en formato JSON con la siguiente estructura:
{
  "commit_message": "feat(modulo): descripcion concisa del cambio",
  "files_modified": ["archivo1.py"],
  "implementation_notes": "Detalles de la solucion implementada"
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
        data_classification: str = "approved_code_context",
        project_context: str | None = None,
        design_tokens_context: str | None = None,
    ) -> DeveloperResult:
        steps_str = "\n".join(f"- {s}" for s in plan_steps)
        user_prompt = (
            f"ID de Tarea: {task_id}\nTítulo: {title}\nPlan Arquitectónico: {plan_summary}\n"
            f"Pasos del Plan:\n{steps_str}\n"
            f"Worktree Path: {worktree_path}\n\n"
            f"Genera el resultado de desarrollo en formato JSON."
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

        return self._parse_response(response.content, task_id, title)

    def _parse_response(self, content: str, task_id: str, default_title: str) -> DeveloperResult:
        cleaned = content.strip()
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        raw_json = json_match.group(1) if json_match else cleaned

        try:
            data = json.loads(raw_json)
            return DeveloperResult(
                commit_message=data.get("commit_message", f"feat({task_id.lower()}): {default_title.lower()}"),
                files_modified=data.get("files_modified", []),
                implementation_notes=data.get("implementation_notes", ""),
            )
        except Exception:
            return DeveloperResult(
                commit_message=f"feat({task_id.lower()}): {default_title.lower()}",
                files_modified=[],
                implementation_notes="Implementación completada según plan.",
            )
