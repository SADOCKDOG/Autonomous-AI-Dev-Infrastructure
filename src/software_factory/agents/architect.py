"""Agente Arquitecto: inspecciona el repositorio y define el plan de cambios técnico."""

import json
import re
from pydantic import BaseModel, Field
from software_factory.agents.base import BaseAgent
from software_factory.model_gateway.base import ChatMessage


class ArchitectPlan(BaseModel):
    summary: str
    affected_files: list[str] = Field(default_factory=list)
    plan_steps: list[str] = Field(default_factory=list)
    technical_risks: list[str] = Field(default_factory=list)


ARCHITECT_SYSTEM_PROMPT = """Eres el Agente Arquitecto de una Software Factory local.
Tu responsabilidad es diseñar el plan técnico de cambios antes de que el Desarrollador modifique ningún archivo.

REGLAS:
1. Diseña cambios modulares, mínimos y desacoplados.
2. Identifica con precisión los archivos afectados.
3. Evalúa riesgos técnicos potenciales (compatibilidad, concurrencia, rendimiento).
4. Responde EXCLUSIVAMENTE un bloque JSON con el siguiente formato:
{
  "summary": "Resumen técnico de la solución propuesta",
  "affected_files": ["ruta/al/archivo1.py", "ruta/al/archivo2.py"],
  "plan_steps": [
    "Paso 1: ...",
    "Paso 2: ..."
  ],
  "technical_risks": [
    "Riesgo 1: ..."
  ]
}
"""


class ArchitectAgent(BaseAgent):
    def __init__(self, gateway=None):
        super().__init__(role="architect", gateway=gateway)

    async def plan_task(
        self,
        task_id: str,
        title: str,
        acceptance_criteria: list[str],
        data_classification: str = "project_context",
    ) -> ArchitectPlan:
        criteria_str = "\n".join(f"- {c}" for c in acceptance_criteria)
        user_prompt = (
            f"ID de Tarea: {task_id}\nTítulo: {title}\n\n"
            f"Criterios de Aceptación a satisfacer:\n{criteria_str}\n\n"
            f"Elabora el plan arquitectónico en formato JSON."
        )

        messages = [
            ChatMessage(role="system", content=ARCHITECT_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_prompt),
        ]

        response = await self.invoke_model(
            messages=messages,
            task_id=task_id,
            data_classification=data_classification,
            temperature=0.1,
        )

        return self._parse_response(response.content, title)

    def _parse_response(self, content: str, default_title: str) -> ArchitectPlan:
        cleaned = content.strip()
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        raw_json = json_match.group(1) if json_match else cleaned

        try:
            data = json.loads(raw_json)
            return ArchitectPlan(
                summary=data.get("summary", f"Plan para {default_title}"),
                affected_files=data.get("affected_files", []),
                plan_steps=data.get("plan_steps", []),
                technical_risks=data.get("technical_risks", []),
            )
        except Exception:
            return ArchitectPlan(
                summary=f"Plan base para {default_title}",
                affected_files=["src/main.py"],
                plan_steps=[f"Implementar requisitos según criterios de aceptación de '{default_title}'"],
                technical_risks=["Revisar tests antes de merge"],
            )
