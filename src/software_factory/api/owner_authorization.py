"""Local API for owner-signed PR authorizations. Unsigned approval is unavailable."""

from pathlib import Path
import os
import json
import re

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from software_factory.git.github_pr import GitHubPRClient, GitHubIntegrationError
from software_factory.orchestration.owner_authorization import OwnerAuthorizationService, OwnerAuthorizationServiceError
from software_factory.security.owner_authorization import (
    OpenSSHOwnerSignatureVerifier,
    SignedOwnerAuthorization,
    SignedOwnerRevocation,
)
from software_factory.settings import settings


router = APIRouter(prefix="/api/v1/owner-authorizations", tags=["Owner PR Authorization"])


class PrepareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    repository: str = Field(min_length=3, max_length=200)
    pr_number: int = Field(gt=0)
    allowed_files: list[str] = Field(min_length=1, max_length=500)
    allow_agent_execution: bool = False
    task_id: str | None = Field(default=None, max_length=100)


def _service() -> OwnerAuthorizationService:
    if not settings.owner_auth_enabled:
        raise HTTPException(status_code=503, detail="Owner authorization is disabled (fail-closed).")
    signer_file = settings.owner_auth_allowed_signers_path
    if not signer_file or not Path(signer_file).is_file():
        raise HTTPException(status_code=503, detail="Trusted owner public-key allowlist is not configured.")
    trusted_root = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "SdogFarm" / "OwnerAuthorization"
    resolved_trust = Path(signer_file).resolve()
    try:
        resolved_trust.relative_to(trusted_root.resolve())
    except ValueError as exc:
        raise HTTPException(
            status_code=503,
            detail="Trusted public-key allowlist must reside outside agent-writable repositories under ProgramData.",
        ) from exc
    if os.access(resolved_trust, os.W_OK) or os.access(resolved_trust.parent, os.W_OK):
        raise HTTPException(
            status_code=503,
            detail="Trusted signer file/directory is writable by the Factory process; protected ACL required.",
        )
    repositories = {
        repo.strip().lower()
        for repo in settings.owner_auth_repositories.split(",")
        if repo.strip()
    }
    if not repositories:
        raise HTTPException(status_code=503, detail="Owner authorization repository allowlist is empty.")
    required_contexts = {
        name.strip()
        for name in settings.owner_auth_required_check_contexts.split(",")
        if name.strip()
    }
    if not required_contexts:
        raise HTTPException(status_code=503, detail="Required product test/analysis/CodeQL check contexts are not configured.")
    try:
        check_app_ids = json.loads(settings.owner_auth_required_check_app_ids_json)
        check_groups = json.loads(settings.owner_auth_check_groups_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=503, detail="Required check app ID policy is invalid.") from exc
    if not isinstance(check_app_ids, dict) or any(not isinstance(value, int) for value in check_app_ids.values()):
        raise HTTPException(status_code=503, detail="Required check app IDs must be a context-to-integer map.")
    if not isinstance(check_groups, dict) or not {"product_tests", "analysis", "codeql"}.issubset(check_groups):
        raise HTTPException(status_code=503, detail="Product test, analysis and CodeQL check groups must be configured.")
    if not settings.owner_auth_signer_identity or not settings.owner_auth_signer_key_id:
        raise HTTPException(status_code=503, detail="Owner signer identity/key fingerprint are not configured.")
    if settings.owner_auth_check_app_id is None:
        raise HTTPException(status_code=503, detail="Trusted GitHub App ID for the owner authorization check is not configured.")
    return OwnerAuthorizationService(
        github=GitHubPRClient(
            owner_authorization_check=settings.owner_auth_check_name,
            owner_authorization_app_id=settings.owner_auth_check_app_id,
        ),
        verifier=OpenSSHOwnerSignatureVerifier(Path(signer_file)),
        allowed_repositories=repositories,
        enabled=True,
        required_check_contexts=required_contexts,
        required_check_app_ids=check_app_ids,
        required_check_groups=check_groups,
    )


def _translate(exc: Exception) -> HTTPException:
    if isinstance(exc, GitHubIntegrationError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, OwnerAuthorizationServiceError):
        message = str(exc)
        status = 409 if any(k in message.lower() for k in ("sha", "revoc", "caduc", "reclam", "consum", "estado", "cambió")) else 422
        return HTTPException(status_code=status, detail=message)
    return HTTPException(status_code=500, detail="Owner authorization failed closed.")


@router.get("/review-context")
def review_context(repository: str = Query(...), pr_number: int = Query(..., gt=0)) -> dict:
    """Read-only snapshot for the Console; it does not authorize or create records."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise HTTPException(status_code=422, detail="repository must use owner/repo format")
    try:
        return GitHubPRClient(owner_authorization_check=settings.owner_auth_check_name).inspect(repository, pr_number).model()
    except GitHubIntegrationError as exc:
        raise _translate(exc) from exc


@router.post("/prepare")
def prepare_owner_authorization(request: PrepareRequest) -> dict:
    """Return unsigned, short-lived review material; this endpoint never grants authority."""
    try:
        payload = _service().prepare(
            request.repository,
            request.pr_number,
            allowed_files=request.allowed_files,
            allow_agent_execution=request.allow_agent_execution,
            task_id=request.task_id,
        )
        from software_factory.security.owner_authorization import canonical_payload, payload_sha256

        return {
            "payload": payload.model_dump(mode="json"),
            "canonical_payload": canonical_payload(payload).decode("utf-8"),
            "payload_sha256": payload_sha256(payload),
            "signature_required": True,
            "authority_granted": False,
        }
    except (GitHubIntegrationError, OwnerAuthorizationServiceError) as exc:
        raise _translate(exc) from exc


@router.post("", status_code=201)
def create_owner_authorization(signed: SignedOwnerAuthorization) -> dict:
    try:
        return _service().authorize(signed)
    except (GitHubIntegrationError, OwnerAuthorizationServiceError) as exc:
        raise _translate(exc) from exc


@router.get("/by-pr")
def active_authorization_for_pr(repository: str = Query(...), pr_number: int = Query(..., gt=0)) -> dict:
    try:
        return _service().get_active_for_pr(repository, pr_number)
    except (GitHubIntegrationError, OwnerAuthorizationServiceError) as exc:
        raise _translate(exc) from exc


@router.get("/history")
def authorization_history(repository: str = Query(...), pr_number: int = Query(..., gt=0)) -> list[dict]:
    try:
        return _service().history_for_pr(repository, pr_number)
    except (GitHubIntegrationError, OwnerAuthorizationServiceError) as exc:
        raise _translate(exc) from exc


@router.get("/{authorization_id}/execution-context")
def prepare_execution_context(authorization_id: str) -> dict:
    try:
        from software_factory.security.owner_authorization import canonical_payload, payload_sha256

        payload = _service().prepare_execution(authorization_id)
        return {
            "payload": payload.model_dump(mode="json"),
            "canonical_payload": canonical_payload(payload).decode("utf-8"),
            "payload_sha256": payload_sha256(payload),
        }
    except (GitHubIntegrationError, OwnerAuthorizationServiceError) as exc:
        raise _translate(exc) from exc


@router.get("/{authorization_id}")
def owner_authorization_status(authorization_id: str) -> dict:
    try:
        return _service().get_status(authorization_id)
    except OwnerAuthorizationServiceError as exc:
        raise _translate(exc) from exc


@router.post("/{authorization_id}/revoke")
def revoke_owner_authorization(authorization_id: str, signed: SignedOwnerRevocation) -> dict:
    if signed.payload.authorization_id != authorization_id:
        raise HTTPException(status_code=422, detail="Path authorization_id differs from signed payload.")
    try:
        return _service().revoke(signed)
    except (GitHubIntegrationError, OwnerAuthorizationServiceError) as exc:
        raise _translate(exc) from exc
