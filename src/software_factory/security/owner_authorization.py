"""SHA-bound, owner-signed authorization primitives for GitHub PR integration.

This module deliberately has no fallback to caller-supplied approver names,
environment secrets, or software keys. Production signing is performed by the
desktop owner console through an external OpenSSH FIDO security key; this
module only verifies signatures and enforces the authorization state machine.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import base64
import struct
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

OWNER_AUTH_NAMESPACE = "owner-merge-authorization-v1"
OWNER_REVOKE_NAMESPACE = "owner-merge-revocation-v1"
OWNER_EXECUTE_NAMESPACE = "owner-merge-execution-v1"
DEFAULT_AUTH_TTL_SECONDS = 900
MAX_AUTH_TTL_SECONDS = 900
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class OwnerAuthorizationError(ValueError):
    """Authorization failed validation or attempted an invalid state transition."""


class AuthorizationScope(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: Literal["MERGE"]
    allowed_files: list[str] = Field(min_length=1, max_length=500)
    allow_agent_execution: bool = False

    @field_validator("allowed_files")
    @classmethod
    def normalize_files(cls, value: list[str]) -> list[str]:
        normalized = sorted(set(path.replace("\\", "/").strip() for path in value))
        if not normalized or any(
            not item
            or item.startswith("/")
            or re.match(r"^[A-Za-z]:", item)
            or ".." in item.split("/")
            or any(ord(char) < 32 or 0x7F <= ord(char) <= 0x9F or 0x202A <= ord(char) <= 0x202E or 0x2066 <= ord(char) <= 0x2069 for char in item)
            for item in normalized
        ):
            raise ValueError("allowed_files debe contener rutas relativas seguras y no vacías")
        return normalized


class OwnerAuthorizationPayload(BaseModel):
    """Canonical owner approval for one repository, PR, SHA, scope and operation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    authorization_id: str
    signer_identity: str = Field(min_length=3, max_length=160)
    github_login: str = Field(min_length=1, max_length=100)
    key_id: str = Field(min_length=8, max_length=128)
    repository: str
    pr_number: int = Field(gt=0)
    head_sha: str
    base_ref: str = Field(min_length=1, max_length=255)
    base_sha: str
    diff_sha256: str
    scope: AuthorizationScope
    decision: Literal["AUTHORIZE_MERGE"]
    issued_at: datetime
    expires_at: datetime
    nonce: str = Field(min_length=32, max_length=128)
    task_id: str | None = Field(default=None, max_length=100)

    @field_validator("authorization_id")
    @classmethod
    def validate_uuid(cls, value: str) -> str:
        return str(UUID(value))

    @field_validator("repository")
    @classmethod
    def validate_repository(cls, value: str) -> str:
        if not REPOSITORY_RE.fullmatch(value):
            raise ValueError("repository debe tener formato owner/repo")
        return value

    @field_validator("head_sha", "base_sha")
    @classmethod
    def validate_sha(cls, value: str) -> str:
        if not SHA_RE.fullmatch(value):
            raise ValueError("se requiere un SHA Git completo de 40 caracteres hexadecimales")
        return value

    @field_validator("diff_sha256")
    @classmethod
    def validate_diff_sha(cls, value: str) -> str:
        if not re.fullmatch(r"^[0-9a-f]{64}$", value):
            raise ValueError("diff_sha256 debe ser SHA-256 hexadecimal de 64 caracteres")
        return value

    @field_validator("issued_at", "expires_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("las fechas deben incluir zona horaria UTC")
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def validate_lifetime(self) -> "OwnerAuthorizationPayload":
        ttl = (self.expires_at - self.issued_at).total_seconds()
        if ttl <= 0 or ttl > MAX_AUTH_TTL_SECONDS:
            raise ValueError(f"la autorización debe caducar en 1..{MAX_AUTH_TTL_SECONDS} segundos")
        if not self.nonce.strip():
            raise ValueError("nonce vacío")
        return self


class SignedOwnerAuthorization(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    payload: OwnerAuthorizationPayload
    signature_format: Literal["openssh-sk"]
    signature: str = Field(min_length=64, max_length=8192)


class OwnerRevocationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    revocation_id: str
    authorization_id: str
    signer_identity: str
    github_login: str
    key_id: str
    repository: str
    pr_number: int = Field(gt=0)
    head_sha: str
    decision: Literal["REVOKE"]
    issued_at: datetime
    nonce: str = Field(min_length=32, max_length=128)

    @field_validator("revocation_id", "authorization_id")
    @classmethod
    def validate_uuids(cls, value: str) -> str:
        return str(UUID(value))

    @field_validator("repository")
    @classmethod
    def validate_repository(cls, value: str) -> str:
        if not REPOSITORY_RE.fullmatch(value):
            raise ValueError("repository debe tener formato owner/repo")
        return value

    @field_validator("head_sha")
    @classmethod
    def validate_sha(cls, value: str) -> str:
        if not SHA_RE.fullmatch(value):
            raise ValueError("se requiere un SHA Git completo")
        return value

    @field_validator("issued_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("issued_at debe incluir zona horaria UTC")
        return value.astimezone(timezone.utc)


class SignedOwnerRevocation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    payload: OwnerRevocationPayload
    signature_format: Literal["openssh-sk"]
    signature: str = Field(min_length=64, max_length=8192)


class OwnerExecutionPayload(BaseModel):
    """Fresh owner signature required when an authorization does not delegate execution."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal[1] = 1
    execution_id: str
    authorization_id: str
    signer_identity: str
    github_login: str
    key_id: str
    repository: str
    pr_number: int = Field(gt=0)
    head_sha: str
    decision: Literal["EXECUTE_MERGE"]
    issued_at: datetime
    nonce: str = Field(min_length=32, max_length=128)

    @field_validator("execution_id", "authorization_id")
    @classmethod
    def validate_uuids(cls, value: str) -> str:
        return str(UUID(value))

    @field_validator("repository")
    @classmethod
    def validate_repository(cls, value: str) -> str:
        if not REPOSITORY_RE.fullmatch(value):
            raise ValueError("repository debe tener formato owner/repo")
        return value

    @field_validator("head_sha")
    @classmethod
    def validate_sha(cls, value: str) -> str:
        if not SHA_RE.fullmatch(value):
            raise ValueError("se requiere un SHA Git completo")
        return value

    @field_validator("issued_at")
    @classmethod
    def require_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() != timedelta(0):
            raise ValueError("issued_at debe incluir zona horaria UTC")
        return value.astimezone(timezone.utc)


class SignedOwnerExecution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    payload: OwnerExecutionPayload
    signature_format: Literal["openssh-sk"]
    signature: str = Field(min_length=64, max_length=8192)


class SignatureVerifier(Protocol):
    def verify(self, signer_identity: str, key_id: str, message: bytes, signature: str, namespace: str) -> bool: ...


def canonical_payload(payload: BaseModel) -> bytes:
    """Stable UTF-8 representation; exactly these bytes are displayed and signed."""
    data = payload.model_dump(mode="json", exclude_none=True)
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def payload_sha256(payload: BaseModel) -> str:
    return hashlib.sha256(canonical_payload(payload)).hexdigest()


def _read_ssh_string(data: bytes, offset: int) -> tuple[bytes, int]:
    if offset + 4 > len(data):
        raise ValueError("truncated SSH string length")
    size = struct.unpack(">I", data[offset:offset + 4])[0]
    start = offset + 4
    end = start + size
    if end > len(data):
        raise ValueError("truncated SSH string")
    return data[start:end], end


def sshsig_fido_flags(signature: str) -> tuple[str, int]:
    """Return the namespace and FIDO flags from armored SSHSIG bytes."""
    lines = [line.strip() for line in signature.splitlines() if line.strip()]
    if len(lines) < 3 or lines[0] != "-----BEGIN SSH SIGNATURE-----" or lines[-1] != "-----END SSH SIGNATURE-----":
        raise ValueError("invalid SSHSIG armor")
    blob = base64.b64decode("".join(lines[1:-1]), validate=True)
    if not blob.startswith(b"SSHSIG") or len(blob) < 10:
        raise ValueError("invalid SSHSIG preamble")
    version = struct.unpack(">I", blob[6:10])[0]
    if version != 1:
        raise ValueError("unsupported SSHSIG version")
    offset = 10
    public_key, offset = _read_ssh_string(blob, offset)
    namespace, offset = _read_ssh_string(blob, offset)
    _reserved, offset = _read_ssh_string(blob, offset)
    _hash_alg, offset = _read_ssh_string(blob, offset)
    signature_field, offset = _read_ssh_string(blob, offset)
    if offset != len(blob):
        raise ValueError("trailing SSHSIG data")

    public_type, pub_cursor = _read_ssh_string(public_key, 0)
    if public_type == b"sk-ssh-ed25519@openssh.com":
        _public_key_bytes, pub_cursor = _read_ssh_string(public_key, pub_cursor)
    elif public_type == b"sk-ecdsa-sha2-nistp256@openssh.com":
        _curve, pub_cursor = _read_ssh_string(public_key, pub_cursor)
        _public_key_bytes, pub_cursor = _read_ssh_string(public_key, pub_cursor)
    else:
        raise ValueError("public key is not FIDO-backed")
    application, pub_cursor = _read_ssh_string(public_key, pub_cursor)
    if pub_cursor != len(public_key) or application != b"ssh:":
        raise ValueError("FIDO key application must be ssh:")
    algorithm, cursor = _read_ssh_string(signature_field, 0)
    if algorithm not in (b"sk-ssh-ed25519@openssh.com", b"sk-ecdsa-sha2-nistp256@openssh.com"):
        raise ValueError("signature is not FIDO-backed")
    if public_type != algorithm:
        raise ValueError("FIDO signature algorithm does not match public key")
    if algorithm == b"sk-ssh-ed25519@openssh.com":
        _raw_signature, cursor = _read_ssh_string(signature_field, cursor)
    else:
        # ECDSA security-key signatures encode r and s as two SSH mpints.
        _r, cursor = _read_ssh_string(signature_field, cursor)
        _s, cursor = _read_ssh_string(signature_field, cursor)
    if cursor + 5 != len(signature_field):
        raise ValueError("invalid FIDO signature payload")
    flags = signature_field[cursor]
    _counter = struct.unpack(">I", signature_field[cursor + 1:cursor + 5])[0]
    return namespace.decode("utf-8"), flags


def require_fido_presence_and_verification(signature: str, namespace: str) -> None:
    """Require FIDO user-presence (0x01) and user-verification (0x04) flags."""
    actual_namespace, flags = sshsig_fido_flags(signature)
    if actual_namespace != namespace:
        raise ValueError("signature namespace mismatch")
    if flags & 0x05 != 0x05:
        raise ValueError("FIDO signature lacks user presence and verification")


class OpenSSHOwnerSignatureVerifier:
    """Verifies FIDO-backed OpenSSH signatures against a protected public allowlist.

    The allowlist must be deployed outside agent-writable worktrees. Production
    entries must use OpenSSH security-key public key types; software keys are
    intentionally rejected by production configuration validation.
    """

    def __init__(self, allowed_signers_file: Path, ssh_keygen: str = "ssh-keygen"):
        self.allowed_signers_file = Path(allowed_signers_file)
        self.ssh_keygen = ssh_keygen

    def _matching_key_line(self, signer_identity: str, key_id: str) -> str | None:
        if not self.allowed_signers_file.is_file():
            return None
        for line in self.allowed_signers_file.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            # Allowed-signers format: identity [options] key-type key-data [comment].
            fields = stripped.split()
            if len(fields) < 3 or fields[0] != signer_identity:
                continue
            key_type_index = next((i for i, field in enumerate(fields) if field.startswith("sk-ssh-") or field.startswith("sk-ecdsa-")), None)
            if key_type_index is None:
                continue
            try:
                public_blob = base64.b64decode(fields[key_type_index + 1], validate=True)
            except (ValueError, IndexError):
                continue
            fingerprint = "SHA256:" + base64.b64encode(hashlib.sha256(public_blob).digest()).decode("ascii").rstrip("=")
            if key_id == fingerprint:
                return stripped
        return None

    def has_trusted_signer(self, signer_identity: str, key_id: str) -> bool:
        return self._matching_key_line(signer_identity, key_id) is not None

    def verify(self, signer_identity: str, key_id: str, message: bytes, signature: str, namespace: str) -> bool:
        matching_line = self._matching_key_line(signer_identity, key_id)
        if matching_line is None:
            return False
        try:
            require_fido_presence_and_verification(signature, namespace)
        except (ValueError, UnicodeDecodeError, struct.error):
            return False
        with tempfile.TemporaryDirectory(prefix="owner-auth-verify-") as temp_dir:
            root = Path(temp_dir)
            message_path = root / "payload.json"
            signature_path = root / "payload.sig"
            allowed_signers_path = root / "allowed_signers"
            message_path.write_bytes(message)
            signature_path.write_text(signature, encoding="ascii")
            allowed_signers_path.write_text(matching_line + "\n", encoding="utf-8")
            try:
                completed = subprocess.run(
                    [
                        self.ssh_keygen,
                        "-Y", "verify",
                        "-f", str(allowed_signers_path),
                        "-I", signer_identity,
                        "-n", namespace,
                        "-s", str(signature_path),
                    ],
                    input=message,
                    capture_output=True,
                    timeout=20,
                    check=False,
                )
            except (OSError, subprocess.TimeoutExpired):
                return False
            return completed.returncode == 0


def validate_payload_time(payload: OwnerAuthorizationPayload, now: datetime | None = None) -> None:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise OwnerAuthorizationError("reloj de validación sin zona horaria")
    if payload.issued_at > current + timedelta(seconds=30):
        raise OwnerAuthorizationError("la autorización está fechada en el futuro")
    if payload.expires_at <= current:
        raise OwnerAuthorizationError("la autorización ha caducado")
    if (payload.expires_at - payload.issued_at).total_seconds() > MAX_AUTH_TTL_SECONDS:
        raise OwnerAuthorizationError("la vigencia supera la política máxima")
