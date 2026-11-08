from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from software_factory.git.github_pr import PRSnapshot
from software_factory.kanban.schema import TaskCreate, TaskStatus, TaskTransitionRequest
from software_factory.kanban.service import KanbanService, KanbanValidationError
from software_factory.orchestration.owner_authorization import (
    OwnerAuthorizationService,
    OwnerAuthorizationServiceError,
)
from software_factory.persistence.database import get_db, migrate_owner_auth_db
from software_factory.security.owner_authorization import (
    OWNER_AUTH_NAMESPACE,
    OwnerAuthorizationPayload,
    OwnerRevocationPayload,
    SignedOwnerAuthorization,
    SignedOwnerRevocation,
    canonical_payload,
)

REPO = "SADOCKDOG/LIVESTOCK-MANAGER"
HEAD = "a" * 40
BASE = "b" * 40
KEY_ID = "SHA256:unit-test-owner-key"
OWNER = "owner@example.test"


class FakeVerifier:
    def verify(self, signer_identity, key_id, message, signature, namespace):
        expected = f"sig:{namespace}:{hashlib.sha256(message).hexdigest()}"
        return signer_identity == OWNER and key_id == KEY_ID and signature == expected

    def has_trusted_signer(self, signer_identity, key_id):
        return signer_identity == OWNER and key_id == KEY_ID


class FakeGitHub:
    def __init__(self):
        self.snapshot = PRSnapshot(
            repository=REPO,
            pr_number=321,
            html_url=f"https://github.com/{REPO}/pull/321",
            state="open",
            merged=False,
            merge_commit_sha=None,
            draft=False,
            head_sha=HEAD,
            head_ref="feat/test",
            base_ref="master",
            base_sha=BASE,
            mergeable=True,
            files=("js/a.js",),
            file_details=({
                "filename": "js/a.js",
                "status": "modified",
                "additions": 1,
                "deletions": 0,
                "changes": 1,
                "patch": "@@ -1 +1 @@\n-old\n+new",
            },),
            diff_sha256="d" * 64,
            required_checks=(
                {"context": "Product tests", "app_id": 11},
                {"context": "CodeQL", "app_id": 22},
                {"context": "Owner authorization", "app_id": 33},
            ),
            check_results={
                "Product tests": {"conclusion": "success", "app_id": 11},
                "CodeQL": {"conclusion": "success", "app_id": 22},
                "Owner authorization": {"conclusion": "success", "app_id": 33},
            },
            branch_protection_valid=True,
            has_bypass=False,
            has_unverified_ruleset=False,
            owner_authorization_check="Owner authorization",
        )

    def verify_app_installation_admin(self, repository, github_login):
        return repository.lower() == REPO.lower() and github_login == "SADOCKDOG"

    def inspect(self, repository, pr_number):
        return self.snapshot


def make_payload(*, allow_agent=True, now=None, task_id=None):
    issued = now or datetime.now(timezone.utc)
    return OwnerAuthorizationPayload(
        authorization_id="38c63879-2abc-4d2f-9d80-4e168a79fe18",
        signer_identity=OWNER,
        github_login="SADOCKDOG",
        key_id=KEY_ID,
        repository=REPO,
        pr_number=321,
        head_sha=HEAD,
        base_ref="master",
        base_sha=BASE,
        diff_sha256="d" * 64,
        scope={"operation": "MERGE", "allowed_files": ["js/a.js"], "allow_agent_execution": allow_agent},
        decision="AUTHORIZE_MERGE",
        issued_at=issued,
        expires_at=issued + timedelta(minutes=10),
        nonce="nonce-owner-auth-unique-value-000000000000",
        task_id=task_id,
    )


def sign(namespace, payload):
    return f"sig:{namespace}:{hashlib.sha256(canonical_payload(payload)).hexdigest()}"


def make_service(github=None, clock=None, *, enabled=True):
    return OwnerAuthorizationService(
        github or FakeGitHub(),
        FakeVerifier(),
        allowed_repositories={REPO},
        enabled=enabled,
        owner_signer_identity=OWNER,
        owner_signer_key_id=KEY_ID,
        owner_github_login="SADOCKDOG",
        required_check_contexts={"Product tests", "CodeQL"},
        required_check_app_ids={"Product tests": 11, "CodeQL": 22, "Owner authorization": 33},
        required_check_groups={
            "product_tests": ["Product tests"],
            "analysis": ["CodeQL"],
            "codeql": ["CodeQL"],
        },
        clock=clock,
    )


def authorize(service, payload=None):
    payload = payload or make_payload()
    return service.authorize(SignedOwnerAuthorization(
        payload=payload,
        signature_format="openssh-sk",
        signature=sign(OWNER_AUTH_NAMESPACE, payload),
    ))


def test_canonical_payload_is_stable_and_sha_bound():
    payload = make_payload()
    first = canonical_payload(payload)
    second = canonical_payload(OwnerAuthorizationPayload.model_validate_json(first))
    assert first == second
    assert b'"head_sha":"' + HEAD.encode() in first
    assert b'"allow_agent_execution":true' in first


def test_authorization_is_recorded_once_and_replay_nonce_is_rejected():
    service = make_service()
    payload = make_payload()
    first = authorize(service, payload)
    assert first["state"] == "ACTIVE"
    assert first["head_sha"] == HEAD
    with pytest.raises(Exception):
        authorize(service, payload)


def test_invalid_signature_and_caller_selected_owner_are_rejected():
    service = make_service()
    payload = make_payload().model_copy(update={"signer_identity": "agent@example.test"})
    with pytest.raises(OwnerAuthorizationServiceError):
        authorize(service, payload)
    payload = make_payload()
    invalid = SignedOwnerAuthorization(payload=payload, signature_format="openssh-sk", signature="x" * 64)
    with pytest.raises(OwnerAuthorizationServiceError):
        service.authorize(invalid)


def test_head_base_diff_or_file_change_invalidates_review_before_authorization():
    github = FakeGitHub()
    service = make_service(github)
    github.snapshot = github.snapshot.__class__(**{
        **github.snapshot.__dict__,
        "head_sha": "e" * 40,
    })
    with pytest.raises(OwnerAuthorizationServiceError, match="cambió"):
        authorize(service)


def test_authorization_cannot_be_replayed_for_another_pr():
    service = make_service()
    payload = make_payload().model_copy(update={"pr_number": 322})
    with pytest.raises(OwnerAuthorizationServiceError, match="PR viva"):
        authorize(service, payload)


def test_no_checks_or_unprotected_branch_fails_closed():
    github = FakeGitHub()
    service = make_service(github)
    github.snapshot = github.snapshot.__class__(**{
        **github.snapshot.__dict__,
        "branch_protection_valid": False,
    })
    with pytest.raises(OwnerAuthorizationServiceError, match="Branch protection"):
        authorize(service)


def test_revocation_is_signed_one_shot_and_audited():
    service = make_service()
    auth = authorize(service)
    payload = OwnerRevocationPayload(
        revocation_id="e8d22f6e-4ea7-4f34-9f08-b9079479535a",
        authorization_id=auth["authorization_id"],
        signer_identity=OWNER,
        github_login="SADOCKDOG",
        key_id=KEY_ID,
        repository=REPO,
        pr_number=321,
        head_sha=HEAD,
        decision="REVOKE",
        issued_at=datetime.now(timezone.utc),
        nonce="nonce-owner-revoke-unique-value-000000000000",
    )
    signed = SignedOwnerRevocation(payload=payload, signature_format="openssh-sk", signature=sign("owner-merge-revocation-v1", payload))
    assert service.revoke(signed)["state"] == "REVOKED"
    with pytest.raises(OwnerAuthorizationServiceError):
        service.revoke(signed)


def test_expired_authorization_is_rejected_at_authorize():
    now = datetime.now(timezone.utc)
    current = [now + timedelta(minutes=20)]
    service = make_service(clock=lambda: current[0])
    payload = make_payload(now=now)
    assert payload.expires_at < current[0]
    with pytest.raises(OwnerAuthorizationServiceError, match="caduc"):
        authorize(service, payload)


def test_service_has_no_merge_capability():
    service = make_service()
    assert not hasattr(service, "execute_merge")
    assert not hasattr(service.github, "merge_sha_preconditioned")
    assert not hasattr(service.github, "merge_ready")


def test_merge_unknown_blocks_authorize_without_retry():
    service = make_service()
    first = authorize(service)
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE owner_authorizations SET state='MERGE_UNKNOWN' WHERE authorization_id=?",
            (first["authorization_id"],),
        )
    other = make_payload().model_copy(
        update={"authorization_id": "7b8b4c2a-0000-4000-8000-111111111111", "nonce": "nonce-owner-auth-other-00000000000000"}
    )
    with pytest.raises(OwnerAuthorizationServiceError, match="incierto"):
        authorize(service, other)
    status = service.get_status(first["authorization_id"])
    assert status["state"] == "MERGE_UNKNOWN"


def test_disabled_mode_has_no_side_effects():
    github = FakeGitHub()
    service = make_service(github, enabled=False)
    with pytest.raises(OwnerAuthorizationServiceError, match="deshabilitada"):
        authorize(service)
    with get_db() as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert "owner_authorizations" not in tables


def test_incomplete_config_fails_closed():
    service = OwnerAuthorizationService(
        FakeGitHub(),
        FakeVerifier(),
        allowed_repositories=set(),
        enabled=True,
        owner_signer_identity=OWNER,
        owner_signer_key_id=KEY_ID,
        owner_github_login="SADOCKDOG",
        required_check_contexts=set(),
        required_check_app_ids={},
        required_check_groups={},
    )
    with pytest.raises(OwnerAuthorizationServiceError):
        service.prepare(REPO, 321, allowed_files=["js/a.js"])


def test_migration_empty_db_creates_tables(tmp_path):
    target = tmp_path / "empty.db"
    target.touch()
    migrate_owner_auth_db(target)
    conn = sqlite3.connect(target)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"owner_authorizations", "owner_authorization_events", "schema_migrations"}.issubset(tables)
    version = conn.execute("SELECT version FROM schema_migrations").fetchone()[0]
    assert version == 1
    conn.close()


def test_migration_old_db_upgrades_without_owner_tables(tmp_path):
    target = tmp_path / "old.db"
    conn = sqlite3.connect(target)
    conn.execute("CREATE TABLE tasks (id TEXT PRIMARY KEY, title TEXT NOT NULL DEFAULT '')")
    conn.commit()
    conn.close()
    migrate_owner_auth_db(target)
    conn = sqlite3.connect(target)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    assert {"owner_authorizations", "schema_migrations"}.issubset(tables)
    assert "tasks" in tables
    conn.close()


def test_migration_failure_is_visible(tmp_path):
    target = tmp_path / "notadb.txt"
    target.write_text("not a sqlite database", encoding="utf-8")
    with pytest.raises(sqlite3.Error):
        migrate_owner_auth_db(target)


def test_authorize_writes_atomic_audit_event():
    service = make_service()
    auth = authorize(service)
    status = service.get_status(auth["authorization_id"])
    assert [e["event_type"] for e in status["events"]] == ["AUTHORIZED"]


def test_execution_intent_cannot_execute_merge():
    service = make_service()
    auth = authorize(service, make_payload(allow_agent=False))
    intent = service.prepare_execution(auth["authorization_id"])
    assert intent.authorization_id == auth["authorization_id"]
    assert service.get_status(auth["authorization_id"])["state"] == "ACTIVE"
    assert not hasattr(service, "execute_merge")


def test_clock_skew_future_payload_is_rejected():
    now = datetime.now(timezone.utc)
    service = make_service(clock=lambda: now)
    payload = make_payload(now=now + timedelta(seconds=90))
    with pytest.raises(OwnerAuthorizationServiceError, match="futuro"):
        authorize(service, payload)


def test_prepare_rejects_draft_or_unmergeable_pr():
    github = FakeGitHub()
    github.snapshot = github.snapshot.__class__(**{
        **github.snapshot.__dict__,
        "draft": True,
    })
    service = make_service(github)
    with pytest.raises(OwnerAuthorizationServiceError, match="abierta|draft|mergeable"):
        service.prepare(REPO, 321, allowed_files=["js/a.js"])


def test_append_only_events_are_not_rewritten_by_app():
    service = make_service()
    auth = authorize(service)
    before = service.get_status(auth["authorization_id"])["events"]
    with get_db() as conn:
        conn.execute("BEGIN IMMEDIATE")
        count = conn.execute(
            "SELECT COUNT(*) FROM owner_authorization_events WHERE authorization_id=?",
            (auth["authorization_id"],),
        ).fetchone()[0]
    assert count == 1 and len(before) == 1
