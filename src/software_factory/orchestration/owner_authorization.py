"""Owner-signed, SHA-bound PR authorization recording (no merge executor).

PR-1 records and validates signed authorizations only. It never writes to
GitHub or merges PRs. MERGE_UNKNOWN can be observed, but reconciliation and
execution arrive with the executor PR.
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Callable
from uuid import uuid4

from software_factory.git.github_pr import GitHubPRClient, PRSnapshot
from software_factory.persistence.database import (
    OWNER_AUTH_SCHEMA_VERSION,
    get_db,
    get_owner_auth_schema_version,
    migrate_owner_auth_db,
)
from software_factory.security.owner_authorization import (
    OWNER_AUTH_NAMESPACE,
    OWNER_REVOKE_NAMESPACE,
    OwnerAuthorizationError as PayloadError,
    OwnerAuthorizationPayload,
    OwnerExecutionPayload,
    OwnerRevocationPayload,
    SignatureVerifier,
    SignedOwnerAuthorization,
    SignedOwnerRevocation,
    canonical_payload,
    validate_payload_time,
)
from software_factory.settings import settings


class OwnerAuthorizationServiceError(RuntimeError):
    """Service-level denial, stale data, or invalid authorization state."""


class OwnerAuthorizationService:
    """Fail-closed PR authorization service. No merge executor in PR-1."""

    def __init__(
        self,
        github: GitHubPRClient,
        verifier: SignatureVerifier,
        *,
        allowed_repositories: set[str] | None = None,
        enabled: bool | None = None,
        max_ttl_seconds: int | None = None,
        owner_signer_identity: str | None = None,
        owner_signer_key_id: str | None = None,
        owner_github_login: str | None = None,
        required_check_contexts: set[str] | None = None,
        required_check_app_ids: dict[str, int] | None = None,
        required_check_groups: dict[str, list[str]] | None = None,
        clock: Callable[[], datetime] | None = None,
    ):
        self.github = github
        self.verifier = verifier
        configured = {
            repo.strip().lower()
            for repo in settings.owner_auth_repositories.split(",")
            if repo.strip()
        }
        self.allowed_repositories = {r.lower() for r in (allowed_repositories if allowed_repositories is not None else configured)}
        self.enabled = settings.owner_auth_enabled if enabled is None else enabled
        self.max_ttl_seconds = min(
            settings.owner_auth_max_ttl_seconds if max_ttl_seconds is None else max_ttl_seconds,
            900,
        )
        self.owner_signer_identity = settings.owner_auth_signer_identity if owner_signer_identity is None else owner_signer_identity
        self.owner_signer_key_id = settings.owner_auth_signer_key_id if owner_signer_key_id is None else owner_signer_key_id
        self.owner_github_login = settings.owner_auth_github_login if owner_github_login is None else owner_github_login
        configured_checks = {
            name.strip()
            for name in settings.owner_auth_required_check_contexts.split(",")
            if name.strip()
        }
        self.required_check_contexts = required_check_contexts if required_check_contexts is not None else configured_checks
        try:
            configured_app_ids = json.loads(settings.owner_auth_required_check_app_ids_json)
        except json.JSONDecodeError:
            configured_app_ids = {}
        self.required_check_app_ids = required_check_app_ids if required_check_app_ids is not None else configured_app_ids
        try:
            configured_groups = json.loads(settings.owner_auth_check_groups_json)
        except json.JSONDecodeError:
            configured_groups = {}
        self.required_check_groups = required_check_groups if required_check_groups is not None else configured_groups
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def migrate() -> object:
        """Explicit operation: apply Owner Auth migration to the configured DB.

        Never called by __init__ or request handlers. Operators must run it
        explicitly (per environment, with authorization) before enabling the API.
        """
        return migrate_owner_auth_db()

    def _require_migrated(self) -> None:
        if get_owner_auth_schema_version() != OWNER_AUTH_SCHEMA_VERSION:
            raise OwnerAuthorizationServiceError(
                "Migración Owner Auth pendiente; aplique migrate_owner_auth_db() explícitamente"
            )

    def _require_enabled(self) -> None:
        if not self.enabled:
            raise OwnerAuthorizationServiceError("La autorización de propietario está deshabilitada; fail-closed")

    def _require_repository(self, repository: str) -> None:
        if repository.lower() not in self.allowed_repositories:
            raise OwnerAuthorizationServiceError("Repositorio fuera de la allowlist de integración")

    def prepare(
        self,
        repository: str,
        pr_number: int,
        *,
        allowed_files: list[str],
        allow_agent_execution: bool = False,
        task_id: str | None = None,
    ) -> OwnerAuthorizationPayload:
        """Create an unsigned review candidate from a fresh GitHub PR snapshot."""
        self._require_enabled()
        self._require_repository(repository)
        signer_identity = self.owner_signer_identity
        key_id = self.owner_signer_key_id
        github_login = self.owner_github_login
        is_trusted = getattr(self.verifier, "has_trusted_signer", lambda *_: False)
        if not signer_identity or not key_id or not github_login or not is_trusted(signer_identity, key_id):
            raise OwnerAuthorizationServiceError("No hay una clave pública de propietario configurada y confiable")
        if not self.github.verify_app_installation_admin(repository, github_login):
            raise OwnerAuthorizationServiceError("La identidad GitHub configurada no tiene permiso admin en el repo")
        snapshot = self.github.inspect(repository, pr_number)
        if snapshot.state != "open" or snapshot.draft or not snapshot.mergeable:
            raise OwnerAuthorizationServiceError("La PR debe estar abierta, mergeable y no ser draft")
        if not snapshot.branch_protection_valid or snapshot.has_bypass:
            raise OwnerAuthorizationServiceError("Branch protection no cumple la política de autorización")
        if set(snapshot.files) != set(allowed_files):
            raise OwnerAuthorizationServiceError("El alcance debe coincidir exactamente con los archivos actuales de la PR")
        self._check_required_policy(snapshot, include_owner_check=False)
        issued_at = self.clock().astimezone(timezone.utc)
        return OwnerAuthorizationPayload(
            authorization_id=str(uuid4()),
            signer_identity=signer_identity,
            github_login=github_login,
            key_id=key_id,
            repository=repository,
            pr_number=pr_number,
            head_sha=snapshot.head_sha,
            base_ref=snapshot.base_ref,
            base_sha=snapshot.base_sha,
            diff_sha256=snapshot.diff_sha256,
            scope={
                "operation": "MERGE",
                "allowed_files": allowed_files,
                "allow_agent_execution": allow_agent_execution,
            },
            decision="AUTHORIZE_MERGE",
            issued_at=issued_at,
            expires_at=issued_at + timedelta(seconds=self.max_ttl_seconds),
            nonce=secrets.token_urlsafe(32),
            task_id=task_id,
        )

    def _check_snapshot(
        self,
        snapshot: PRSnapshot,
        payload: OwnerAuthorizationPayload,
        *,
        include_owner_check: bool,
    ) -> None:
        self._require_repository(payload.repository)
        if payload.github_login.lower() != self.owner_github_login.lower():
            raise OwnerAuthorizationServiceError("La identidad GitHub no coincide con el owner configurado")
        if not self.github.verify_app_installation_admin(payload.repository, payload.github_login):
            raise OwnerAuthorizationServiceError("La identidad firmante ya no tiene permisos admin en el repo")
        if snapshot.repository.lower() != payload.repository.lower() or snapshot.pr_number != payload.pr_number:
            raise OwnerAuthorizationServiceError("La PR viva no coincide con el payload firmado")
        if snapshot.state != "open" or snapshot.draft or not snapshot.mergeable:
            raise OwnerAuthorizationServiceError("La PR no está abierta, no es mergeable o sigue en draft")
        if (
            snapshot.head_sha != payload.head_sha
            or snapshot.base_ref != payload.base_ref
            or snapshot.base_sha != payload.base_sha
            or snapshot.diff_sha256 != payload.diff_sha256
        ):
            raise OwnerAuthorizationServiceError("El contenido/base de la PR cambió desde la revisión firmada")
        if set(snapshot.files) != set(payload.scope.allowed_files):
            raise OwnerAuthorizationServiceError("El manifiesto de archivos no coincide exactamente con el alcance firmado")
        if not snapshot.branch_protection_valid or snapshot.has_bypass:
            raise OwnerAuthorizationServiceError("Branch protection no cumple la política; bypass o checks obligatorios ausentes")
        self._check_required_policy(snapshot, include_owner_check=include_owner_check)

    def _check_required_policy(self, snapshot: PRSnapshot, *, include_owner_check: bool) -> None:
        required_contexts = {item["context"] for item in snapshot.required_checks}
        if not self.required_check_contexts:
            raise OwnerAuthorizationServiceError("No hay una allowlist estable de status checks obligatorios configurada")
        required_group_names = {"product_tests", "analysis", "codeql"}
        if not required_group_names.issubset(self.required_check_groups) or any(
            not isinstance(self.required_check_groups.get(group), list) or not self.required_check_groups[group]
            for group in required_group_names
        ):
            raise OwnerAuthorizationServiceError("La política debe exigir grupos de product_tests, analysis y codeql")
        grouped_contexts = {context for group in required_group_names for context in self.required_check_groups[group]}
        if not grouped_contexts.issubset(self.required_check_contexts):
            raise OwnerAuthorizationServiceError("Los contextos por categoría deben estar en la allowlist obligatoria")
        expected = set(self.required_check_contexts)
        if include_owner_check:
            expected.add(snapshot.owner_authorization_check)
        if not expected.issubset(required_contexts):
            raise OwnerAuthorizationServiceError("Branch protection no exige todos los checks de política configurados")
        required_app_by_context = {item["context"]: item.get("app_id") for item in snapshot.required_checks}
        if not self.required_check_app_ids:
            raise OwnerAuthorizationServiceError("No hay allowlist de GitHub App IDs para los checks obligatorios")
        for context in expected:
            pinned_app = self.required_check_app_ids.get(context)
            if pinned_app is None or required_app_by_context.get(context) != pinned_app:
                raise OwnerAuthorizationServiceError(f"El origen GitHub App de {context} no coincide con la política fija")
        if include_owner_check and snapshot.owner_authorization_check not in {
            item["context"] for item in snapshot.required_checks
        }:
            raise OwnerAuthorizationServiceError("Falta el status check obligatorio de owner-authorization")
        if not snapshot.required_checks_pass(include_owner_authorization=include_owner_check):
            raise OwnerAuthorizationServiceError("Hay checks requeridos ausentes, pendientes o fallidos para este HEAD")

    def authorize(self, signed: SignedOwnerAuthorization) -> dict:
        self._require_enabled()
        self._require_migrated()
        payload = signed.payload
        self._require_repository(payload.repository)
        if (
            payload.signer_identity != self.owner_signer_identity
            or payload.key_id != self.owner_signer_key_id
            or payload.github_login.lower() != self.owner_github_login.lower()
        ):
            raise OwnerAuthorizationServiceError("La identidad/clave no corresponde al único propietario configurado")
        if not self.github.verify_app_installation_admin(payload.repository, payload.github_login):
            raise OwnerAuthorizationServiceError("El signer ya no tiene permiso admin sobre el repo")
        try:
            validate_payload_time(payload, self.clock())
        except PayloadError as exc:
            raise OwnerAuthorizationServiceError(str(exc)) from exc
        if (payload.expires_at - payload.issued_at).total_seconds() > self.max_ttl_seconds:
            raise OwnerAuthorizationServiceError("La vigencia supera el máximo configurado")
        message = canonical_payload(payload)
        if not self.verifier.verify(payload.signer_identity, payload.key_id, message, signed.signature, OWNER_AUTH_NAMESPACE):
            raise OwnerAuthorizationServiceError("Firma del propietario inválida o no confiable")
        snapshot = self.github.inspect(payload.repository, payload.pr_number)
        self._check_snapshot(snapshot, payload, include_owner_check=False)

        payload_json = message.decode("utf-8")
        with get_db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            now_iso = self.clock().astimezone(timezone.utc).isoformat()
            expired_rows = conn.execute(
                "SELECT authorization_id FROM owner_authorizations WHERE repository=? AND pr_number=? AND state='ACTIVE' AND expires_at<=?",
                (payload.repository, payload.pr_number, now_iso),
            ).fetchall()
            for expired in expired_rows:
                conn.execute(
                    "UPDATE owner_authorizations SET state='EXPIRED' WHERE authorization_id=? AND state='ACTIVE'",
                    (expired["authorization_id"],),
                )
                self._append_event(conn, expired["authorization_id"], "EXPIRED", "verifier", {"reason": "authorization ttl elapsed"})
            active = conn.execute(
                "SELECT authorization_id FROM owner_authorizations WHERE repository=? AND pr_number=? AND state IN ('ACTIVE','IN_PROGRESS','MERGE_UNKNOWN')",
                (payload.repository, payload.pr_number),
            ).fetchone()
            if active:
                raise OwnerAuthorizationServiceError("Existe una autorización activa o un merge en estado incierto; requiere reconciliación")
            conn.execute(
                """INSERT INTO owner_authorizations (
                    authorization_id, task_id, repository, pr_number, head_sha, base_ref, base_sha,
                    diff_sha256, scope_json, decision, signer_identity, github_login, key_id, issued_at, expires_at,
                    nonce, payload_json, signature, state
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'AUTHORIZE_MERGE', ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE')""",
                (
                    payload.authorization_id,
                    payload.task_id,
                    payload.repository,
                    payload.pr_number,
                    payload.head_sha,
                    payload.base_ref,
                    payload.base_sha,
                    snapshot.diff_sha256,
                    payload.scope.model_dump_json(),
                    payload.signer_identity,
                    payload.github_login,
                    payload.key_id,
                    payload.issued_at.isoformat(),
                    payload.expires_at.isoformat(),
                    payload.nonce,
                    payload_json,
                    signed.signature,
                ),
            )
            self._append_event(conn, payload.authorization_id, "AUTHORIZED", payload.signer_identity, {
                "repository": payload.repository,
                "pr_number": payload.pr_number,
                "head_sha": payload.head_sha,
                "base_ref": payload.base_ref,
                "base_sha": payload.base_sha,
                "diff_sha256": snapshot.diff_sha256,
                "scope": payload.scope.model_dump(mode="json"),
            })
        return self.get_status(payload.authorization_id)

    def revoke(self, signed: SignedOwnerRevocation) -> dict:
        self._require_enabled()
        self._require_migrated()
        payload = signed.payload
        self._require_repository(payload.repository)
        if (
            payload.signer_identity != self.owner_signer_identity
            or payload.key_id != self.owner_signer_key_id
            or payload.github_login.lower() != self.owner_github_login.lower()
        ):
            raise OwnerAuthorizationServiceError("La revocación no está firmada por la clave activa del propietario")
        if not self.github.verify_app_installation_admin(payload.repository, payload.github_login):
            raise OwnerAuthorizationServiceError("El signer ya no tiene permisos admin para revocar")
        age = (self.clock() - payload.issued_at).total_seconds()
        if age < -30 or age > 120:
            raise OwnerAuthorizationServiceError("La revocación debe estar firmada en los últimos 120 segundos")
        if not self.verifier.verify(payload.signer_identity, payload.key_id, canonical_payload(payload), signed.signature, OWNER_REVOKE_NAMESPACE):
            raise OwnerAuthorizationServiceError("Firma de revocación inválida")

        with get_db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT * FROM owner_authorizations WHERE authorization_id=?",
                (payload.authorization_id,),
            ).fetchone()
            if not row:
                raise OwnerAuthorizationServiceError("Autorización desconocida")
            if (
                row["repository"].lower() != payload.repository.lower()
                or row["pr_number"] != payload.pr_number
                or row["head_sha"] != payload.head_sha
                or row["signer_identity"] != payload.signer_identity
                or row["github_login"].lower() != payload.github_login.lower()
                or payload.github_login.lower() != self.owner_github_login.lower()
                or row["key_id"] != payload.key_id
            ):
                raise OwnerAuthorizationServiceError("La revocación no corresponde al payload autorizado")
            if row["state"] != "ACTIVE":
                raise OwnerAuthorizationServiceError("Solo se puede revocar una autorización activa no consumida")
            conn.execute(
                "UPDATE owner_authorizations SET state='REVOKED' WHERE authorization_id=? AND state='ACTIVE'",
                (payload.authorization_id,),
            )
            self._append_event(conn, payload.authorization_id, "REVOKED", payload.signer_identity, {
                "revocation_id": payload.revocation_id,
                "nonce": payload.nonce,
            })
            conn.execute(
                "INSERT INTO owner_authorization_nonces (nonce, authorization_id, purpose) VALUES (?, ?, 'REVOKE')",
                (payload.nonce, payload.authorization_id),
            )
        return self.get_status(payload.authorization_id)

    def get_active_for_pr(self, repository: str, pr_number: int) -> dict:
        self._require_repository(repository)
        self._require_migrated()
        with get_db() as conn:
            row = conn.execute(
                "SELECT authorization_id FROM owner_authorizations WHERE repository=? AND pr_number=? AND state='ACTIVE' AND expires_at>? ORDER BY issued_at DESC LIMIT 1",
                (repository, pr_number, self.clock().astimezone(timezone.utc).isoformat()),
            ).fetchone()
        if not row:
            raise OwnerAuthorizationServiceError("No hay autorización activa para esta PR")
        return self.get_status(row["authorization_id"])

    def history_for_pr(self, repository: str, pr_number: int) -> list[dict]:
        self._require_repository(repository)
        self._require_migrated()
        with get_db() as conn:
            rows = conn.execute(
                "SELECT authorization_id FROM owner_authorizations WHERE repository=? AND pr_number=? ORDER BY issued_at DESC LIMIT 25",
                (repository, pr_number),
            ).fetchall()
        return [self.get_status(row["authorization_id"]) for row in rows]

    def prepare_execution(self, authorization_id: str) -> OwnerExecutionPayload:
        self._require_enabled()
        self._require_migrated()
        with get_db() as conn:
            row = conn.execute(
                "SELECT * FROM owner_authorizations WHERE authorization_id=?",
                (authorization_id,),
            ).fetchone()
        if not row or row["state"] != "ACTIVE":
            raise OwnerAuthorizationServiceError("Autorización no activa")
        authorization = OwnerAuthorizationPayload.model_validate_json(row["payload_json"])
        try:
            validate_payload_time(authorization, self.clock())
        except PayloadError as exc:
            self._transition_state(authorization_id, "EXPIRED", "EXPIRED", authorization.signer_identity, {})
            raise OwnerAuthorizationServiceError("Autorización caducada") from exc
        if authorization.scope.allow_agent_execution:
            raise OwnerAuthorizationServiceError("La autorización delega ejecución al agente y no admite firma owner separada")
        snapshot = self.github.inspect(authorization.repository, authorization.pr_number)
        self._check_snapshot(snapshot, authorization, include_owner_check=True)
        now = self.clock().astimezone(timezone.utc)
        return OwnerExecutionPayload(
            execution_id=str(uuid4()),
            authorization_id=authorization_id,
            signer_identity=authorization.signer_identity,
            github_login=authorization.github_login,
            key_id=authorization.key_id,
            repository=authorization.repository,
            pr_number=authorization.pr_number,
            head_sha=authorization.head_sha,
            decision="EXECUTE_MERGE",
            issued_at=now,
            nonce=secrets.token_urlsafe(32),
        )

    def _transition_state(self, authorization_id: str, state: str, event: str, actor: str, details: dict) -> None:
        with get_db() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                "SELECT state FROM owner_authorizations WHERE authorization_id=?",
                (authorization_id,),
            ).fetchone()
            if not row:
                raise OwnerAuthorizationServiceError("Autorización no encontrada")
            if row["state"] in ("CONSUMED", "REVOKED", "FAILED", "MERGE_UNKNOWN"):
                raise OwnerAuthorizationServiceError(f"Estado terminal: {row['state']}")
            conn.execute("UPDATE owner_authorizations SET state=? WHERE authorization_id=?", (state, authorization_id))
            self._append_event(conn, authorization_id, event, actor, details)

    def get_status(self, authorization_id: str) -> dict:
        self._require_migrated()
        with get_db() as conn:
            row = conn.execute(
                "SELECT authorization_id, task_id, repository, pr_number, head_sha, base_ref, base_sha, diff_sha256, scope_json, signer_identity, github_login, key_id, issued_at, expires_at, state, merge_sha FROM owner_authorizations WHERE authorization_id=?",
                (authorization_id,),
            ).fetchone()
            if not row:
                raise OwnerAuthorizationServiceError("Autorización no encontrada")
            events = conn.execute(
                "SELECT event_type, actor, details, created_at FROM owner_authorization_events WHERE authorization_id=? ORDER BY created_at, event_id",
                (authorization_id,),
            ).fetchall()
        state = row["state"]
        if state == "ACTIVE" and datetime.fromisoformat(row["expires_at"]) <= self.clock():
            state = "EXPIRED"
        return {
            "authorization_id": row["authorization_id"],
            "task_id": row["task_id"],
            "repository": row["repository"],
            "pr_number": row["pr_number"],
            "head_sha": row["head_sha"],
            "base_ref": row["base_ref"],
            "base_sha": row["base_sha"],
            "diff_sha256": row["diff_sha256"],
            "scope": json.loads(row["scope_json"]),
            "signer_identity": row["signer_identity"],
            "github_login": row["github_login"],
            "key_id": row["key_id"],
            "issued_at": row["issued_at"],
            "expires_at": row["expires_at"],
            "state": state,
            "merge_sha": row["merge_sha"],
            "events": [dict(e) for e in events],
        }

    @staticmethod
    def _append_event(conn, authorization_id: str, event_type: str, actor: str, details: dict) -> None:
        conn.execute(
            "INSERT INTO owner_authorization_events (event_id, authorization_id, event_type, actor, details) VALUES (?, ?, ?, ?, ?)",
            (str(uuid4()), authorization_id, event_type, actor, json.dumps(details, sort_keys=True, separators=(",", ":"))),
        )
