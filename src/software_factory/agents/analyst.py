"""Agente Analista / Product Owner."""

import json
import re
from typing import Any
from pydantic import BaseModel, Field
from software_factory.agents.base import BaseAgent
from software_factory.model_gateway.base import ChatMessage


class AnalystResult(BaseModel):
    summary: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    suggested_priority: str = "medium"
    functional_scope: list[str] = Field(default_factory=list)


ANALYST_SYSTEM_PROMPT = """Eres el Agente Analista / Product Owner de una Software Factory de ingeniería rigurosa.
Tu función es analizar la tarjeta de trabajo, clarificar requerimientos y generar una lista de criterios de aceptación verificables y ejecutables por el equipo de QA y desarrollo.

REGLAS ESTRICTAS:
1. No escribas código ejecutable final ni modifiques repositorios.
2. Cada criterio de aceptación debe ser conciso, unívoco y comprobable mediante un test o inspección de diff.
3. Debes responder EXCLUSIVAMENTE un bloque JSON válido con el siguiente formato:
{
  "summary": "Resumen claro del requerimiento",
  "acceptance_criteria": [
    "Criterio 1: ...",
    "Criterio 2: ..."
  ],
  "suggested_priority": "medium",
  "functional_scope": [
    "Módulo o componente afectado 1",
    "Módulo o componente afectado 2"
  ]
}
"""


class AnalystAgent(BaseAgent):
    def __init__(self, gateway=None):
        super().__init__(role="analyst", gateway=gateway)

    async def analyze_task(
        self,
        task_id: str,
        title: str,
        description: str,
        data_classification: str = "project_context",
    ) -> AnalystResult:
        user_prompt = f"ID de Tarea: {task_id}\nTítulo: {title}\nDescripción: {description or 'Sin descripción adicional'}\n\nAnaliza los requerimientos y emite los criterios de aceptación en formato JSON."

        messages = [
            ChatMessage(role="system", content=ANALYST_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_prompt),
        ]

        response = await self.invoke_model(
            messages=messages,
            task_id=task_id,
            data_classification=data_classification,
            temperature=0.1,
        )

        return self._parse_response(response.content, title)

    def _parse_response(self, content: str, default_title: str) -> AnalystResult:
        """Parsea la salida del modelo extrayendo el bloque JSON o usando heurística de respaldo."""
        cleaned = content.strip()
        
        # Intentar extraer bloque JSON si viene envuelto en markdown
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        raw_json = json_match.group(1) if json_match else cleaned

        try:
            data = json.loads(raw_json)
            criteria = data.get("acceptance_criteria", [])
            # Filtrar vacíos
            clean_criteria = [str(c).strip() for c in criteria if str(c).strip()]
            if clean_criteria:
                return AnalystResult(
                    summary=data.get("summary", default_title),
                    acceptance_criteria=clean_criteria,
                    suggested_priority=data.get("suggested_priority", "medium"),
                    functional_scope=data.get("functional_scope", []),
                )
        except Exception:
            pass

        # Heurística de respaldo si el modelo no devuelve JSON estricto
        bullet_lines = []
        for line in cleaned.splitlines():
            line_str = line.strip()
            if line_str.startswith(("-", "*", "•")) or re.match(r"^\d+\.", line_str):
                cleaned_line = re.sub(r"^[-*•\d\.]+\s*", "", line_str).strip()
                if cleaned_line:
                    bullet_lines.append(cleaned_line)

        if not bullet_lines:
            bullet_lines = [f"Verificar que '{default_title}' cumple con los requisitos esperados y pasa los tests."]

        return AnalystResult(
            summary=default_title,
            acceptance_criteria=bullet_lines,
            suggested_priority="medium",
            functional_scope=["Core"],
        )
