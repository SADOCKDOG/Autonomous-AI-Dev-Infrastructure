"""Escáner de seguridad para detección de secretos y credenciales en git diff."""

import re
from pydantic import BaseModel


class SecretFinding(BaseModel):
    rule: str
    line_number: int | None
    matched_snippet: str
    severity: str = "critical"


SECRET_PATTERNS = [
    ("Clave privada RSA/SSH", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("Token de GitHub", re.compile(r"gh[pousr]_[A-Za-z0-9_]{36,255}")),
    ("Token de OpenAI", re.compile(r"sk-[A-Za-z0-9]{32,}")),
    ("Clave AWS Access Key", re.compile(r"(?:A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}")),
    ("Clave Google Cloud/AI", re.compile(r"AIza[0-9A-Za-z-_]{35}")),
    ("Token Bearer en código", re.compile(r"(?:bearer\s+[a-zA-Z0-9\._\-]{20,})", re.IGNORECASE)),
    ("Asignación de contraseña en texto plano", re.compile(r'(?:password|secret|api_key|token)\s*[:=]\s*["\'][^"\']{8,}["\']', re.IGNORECASE)),
]


class SecretScanner:
    """Escanea contenido o diffs de Git buscando credenciales antes de confirmar cambios."""

    @classmethod
    def scan_diff(cls, diff_text: str) -> list[SecretFinding]:
        findings: list[SecretFinding] = []
        lines = diff_text.splitlines()

        for idx, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            # Solo analizar líneas añadidas en el diff
            if line.startswith("+") and not line.startswith("+++"):
                content_to_check = line[1:].strip()
                for rule_name, pattern in SECRET_PATTERNS:
                    match = pattern.search(content_to_check)
                    if match:
                        matched_str = match.group(0)
                        # Redactar parte del secreto para no exponerlo en el informe
                        redacted = matched_str[:4] + "..." + matched_str[-4:] if len(matched_str) > 8 else "***"
                        findings.append(
                            SecretFinding(
                                rule=rule_name,
                                line_number=idx,
                                matched_snippet=f"{line[:10]}... [REDACTED {redacted}]",
                                severity="critical",
                            )
                        )
        return findings

    @classmethod
    def scan_content(cls, content: str) -> list[SecretFinding]:
        findings: list[SecretFinding] = []
        for idx, line in enumerate(content.splitlines(), start=1):
            for rule_name, pattern in SECRET_PATTERNS:
                match = pattern.search(line)
                if match:
                    findings.append(
                        SecretFinding(
                            rule=rule_name,
                            line_number=idx,
                            matched_snippet="[SECRETO DETECTADO]",
                            severity="critical",
                        )
                    )
        return findings
