"""FIDO-backed OpenSSH signer with its own interactive confirmation process."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

AUTH_NAMESPACE = "owner-merge-authorization-v1"
REVOKE_NAMESPACE = "owner-merge-revocation-v1"
ALLOWED_KEY_TYPES = {"sk-ssh-ed25519@openssh.com", "sk-ecdsa-sha2-nistp256@openssh.com"}


class OwnerSignerError(RuntimeError):
    """Fail-closed FIDO signing error."""


def canonical_json(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def public_key_fingerprint(public_key_path: Path) -> tuple[str, str]:
    fields = Path(public_key_path).read_text(encoding="ascii").strip().split()
    if len(fields) < 2 or fields[0] not in ALLOWED_KEY_TYPES:
        raise OwnerSignerError("Se exige una clave OpenSSH FIDO (ed25519-sk o ecdsa-sk)")
    try:
        public_blob = base64.b64decode(fields[1], validate=True)
    except ValueError as exc:
        raise OwnerSignerError("La clave pública FIDO está malformada") from exc
    fingerprint = "SHA256:" + base64.b64encode(hashlib.sha256(public_blob).digest()).decode("ascii").rstrip("=")
    return fields[0], fingerprint


def _broker_sign(
    payload: dict[str, Any], *, key_handle_path: Path, expected_key_id: str,
    namespace: str, signature_output: Path, input_fn: Callable[[str], str],
    run_command: Callable[..., Any], output_fn: Callable[[str], None] = print,
    ssh_keygen: str = "ssh-keygen", timeout_seconds: int = 120,
) -> str:
    if namespace not in {AUTH_NAMESPACE, REVOKE_NAMESPACE}:
        raise OwnerSignerError("Namespace de firma no permitido")
    head_sha = str(payload.get("head_sha", ""))
    if len(head_sha) != 40:
        raise OwnerSignerError("Payload sin SHA HEAD completo")
    handle = Path(key_handle_path).expanduser().resolve(strict=True)
    _, actual_key_id = public_key_fingerprint(Path(str(handle) + ".pub"))
    if actual_key_id != expected_key_id:
        raise OwnerSignerError("La clave FIDO seleccionada no coincide con el key_id confiable")

    message = canonical_json(payload)
    output_fn("AUTORIZACIÓN DE INTEGRACIÓN — CONFIRMACIÓN DEL PROPIETARIO")
    output_fn(f"Repositorio: {payload.get('repository')}")
    output_fn(f"PR: #{payload.get('pr_number')}")
    output_fn(f"HEAD SHA: {head_sha}")
    output_fn(f"Base: {payload.get('base_ref')} @ {payload.get('base_sha')}")
    output_fn(f"Alcance: {json.dumps(payload.get('scope', {}), ensure_ascii=True, sort_keys=True)}")
    output_fn(f"Decisión: {payload.get('decision')}")
    output_fn(f"Caduca: {payload.get('expires_at', 'N/A')}")
    output_fn(f"Payload SHA-256: {hashlib.sha256(message).hexdigest()}")
    output_fn("Payload completo (caracteres de control/Unicode escapados):")
    output_fn(json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=True))
    output_fn("La clave privada permanece en el token FIDO. Se requiere confirmación interactiva y presencia física.")
    if input_fn(f"Escribe los últimos 12 caracteres de HEAD ({head_sha[-12:]}): ").strip() != head_sha[-12:]:
        raise OwnerSignerError("Confirmación del SHA incorrecta; no se firmó")

    with tempfile.TemporaryDirectory(prefix="owner-auth-sign-") as temp_dir:
        payload_path = Path(temp_dir) / "authorization.json"
        signature_path = Path(str(payload_path) + ".sig")
        payload_path.write_bytes(message)
        command = [ssh_keygen, "-Y", "sign", "-f", str(handle), "-n", namespace, str(payload_path)]
        try:
            result = run_command(command, stdin=None, stdout=None, stderr=None, timeout=timeout_seconds, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise OwnerSignerError("No se completó la operación FIDO; no se concedió autorización") from exc
        if result.returncode != 0 or not signature_path.is_file():
            raise OwnerSignerError("La firma FIDO falló o se canceló; no se concedió autorización")
        signature = signature_path.read_text(encoding="ascii")
        if "BEGIN SSH SIGNATURE" not in signature or "END SSH SIGNATURE" not in signature:
            raise OwnerSignerError("Formato de firma OpenSSH inválido")
        Path(signature_output).write_text(signature, encoding="ascii")
        return signature


def sign_owner_payload(
    payload: dict[str, Any], *, key_handle_path: Path, expected_key_id: str,
    namespace: str = AUTH_NAMESPACE, ssh_keygen: str = "ssh-keygen",
    timeout_seconds: int = 120,
) -> str:
    """Spawn a separate visible broker; no caller-supplied confirmation token."""
    handle = Path(key_handle_path).expanduser().resolve(strict=True)
    with tempfile.TemporaryDirectory(prefix="owner-auth-broker-") as temp_dir:
        root = Path(temp_dir)
        payload_path = root / "payload.json"
        signature_path = root / "payload.sig"
        result_path = root / "result.json"
        payload_path.write_bytes(canonical_json(payload))
        command = [sys.executable, str(Path(__file__).resolve()), "--owner-sign-broker", str(payload_path), str(handle), expected_key_id, namespace, str(signature_path), ssh_keygen, str(result_path)]
        creationflags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0) if os.name == "nt" else 0
        try:
            completed = subprocess.run(
                command, stdin=None, stdout=None, stderr=None,
                timeout=timeout_seconds + 30, check=False, creationflags=creationflags,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise OwnerSignerError("No se completó la confirmación interactiva FIDO") from exc
        if completed.returncode != 0 or not result_path.is_file() or not signature_path.is_file():
            raise OwnerSignerError("No se firmó: broker cancelado, sin hardware o con error")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        if result.get("payload_sha256") != hashlib.sha256(canonical_json(payload)).hexdigest():
            raise OwnerSignerError("El broker devolvió resultado ligado a otro payload")
        return signature_path.read_text(encoding="ascii")


def _broker_main(argv: list[str]) -> int:
    if len(argv) != 8 or argv[0] != "--owner-sign-broker":
        return 2
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    _, payload_arg, key_handle_arg, key_id, namespace, signature_arg, ssh_keygen, result_arg = argv
    payload_path = Path(payload_arg)
    key_handle = Path(key_handle_arg)
    signature_path = Path(signature_arg)
    result_path = Path(result_arg)
    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        _broker_sign(
            payload, key_handle_path=key_handle, expected_key_id=key_id,
            namespace=namespace, signature_output=signature_path,
            input_fn=input, run_command=subprocess.run, ssh_keygen=ssh_keygen,
        )
        result_path.write_text(json.dumps({"payload_sha256": hashlib.sha256(canonical_json(payload)).hexdigest()}), encoding="utf-8")
        return 0
    except Exception as exc:
        print(f"Firma cancelada: {type(exc).__name__}. No se concedió autorización.")
        return 1


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "--owner-sign-broker":
    raise SystemExit(_broker_main(sys.argv[1:]))
