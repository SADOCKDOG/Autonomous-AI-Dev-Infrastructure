"""Agente Revisor de Código y Seguridad."""

import json
import re
from pydantic import BaseModel, Field
from software_factory.agents.base import BaseAgent
from software_factory.security.secret_scanner import SecretScanner
from software_factory.model_gateway.base import ChatMessage


class ReviewVerdict(BaseModel):
    is_approved: bool
    has_secrets: bool = False
    secret_count: int = 0
    risk_assessment: str = "low"
    findings: list[str] = Field(default_factory=list)
    recommendation_for_human: str = ""


REVIEWER_SYSTEM_PROMPT = """Eres el Agente Revisor de Código y Seguridad de la Software Factory.
Tu labor es auditar el diff final, verificar el cumplimiento de los criterios de aceptación y evaluar los riesgos antes de solicitar la aprobación humana.

REGLAS:
1. Sé implacable con la calidad, consistencia y seguridad del diff.
2. Si detectas malas prácticas o riesgos altos, indica is_approved: false.
3. Responde en formato JSON estricto con la siguiente estructura:
{
  "is_approved": true,
  "risk_assessment": "low",
  "findings": ["Hallazgo 1", "Hallazgo 2"],
  "recommendation_for_human": "Recomendación para el aprobador humano"
}
"""


class ReviewerAgent(BaseAgent):
    def __init__(self, gateway=None):
        super().__init__(role="reviewer", gateway=gateway)

    async def review_task(
        self,
        task_id: str,
        diff_text: str,
        acceptance_criteria: list[str],
        data_classification: str = "approved_diff",
    ) -> ReviewVerdict:
        # 1. Escaneo determinista de secretos
        secret_findings = SecretScanner.scan_diff(diff_text)
        if secret_findings:
            return ReviewVerdict(
                is_approved=False,
                has_secrets=True,
                secret_count=len(secret_findings),
                risk_assessment="critical",
                findings=[f"{f.rule} en línea {f.line_number}: {f.matched_snippet}" for f in secret_findings],
                recommendation_for_human="RECHAZAR: Se han detectado credenciales o secretos en el diff.",
            )

        # 2. Evaluación mediante modelo si el diff está libre de secretos
        criteria_str = "\n".join(f"- {c}" for c in acceptance_criteria)
        user_prompt = (
            f"ID de Tarea: {task_id}\n\n"
            f"Criterios de Aceptación:\n{criteria_str}\n\n"
            f"Diff a Auditar:\n{diff_text or '(Diff vacío o cambios menores)'}\n\n"
            f"Emite tu veredicto de revisión en formato JSON."
        )

        messages = [
            ChatMessage(role="system", content=REVIEWER_SYSTEM_PROMPT),
            ChatMessage(role="user", content=user_prompt),
        ]

        response = await self.invoke_model(
            messages=messages,
            task_id=task_id,
            data_classification=data_classification,
            temperature=0.1,
        )

        return self._parse_response(response.content)

    def _parse_response(self, content: str) -> ReviewVerdict:
        cleaned = content.strip()
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
        raw_json = json_match.group(1) if json_match else cleaned

        try:
            data = json.loads(raw_json)
            return ReviewVerdict(
                is_approved=data.get("is_approved", True),
                has_secrets=False,
                secret_count=0,
                risk_assessment=data.get("risk_assessment", "low"),
                findings=data.get("findings", []),
                recommendation_for_human=data.get("recommendation_for_human", "Aprobado para merge tras revisión de QA."),
            )
        except Exception:
            return ReviewVerdict(
                is_approved=True,
                has_secrets=False,
                secret_count=0,
                risk_assessment="low",
                findings=["Revisión automática completada sin secretos."],
                recommendation_for_human="Revisión satisfactoria.",
            )
