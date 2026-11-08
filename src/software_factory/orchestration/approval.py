"""Deprecated unsigned approval API; PR integration uses signed owner authorizations."""

from typing import Literal
from pydantic import BaseModel


class UnsignedApprovalDisabled(RuntimeError):
    """Raised when legacy caller-supplied approval is attempted."""


class HumanApprovalRequest(BaseModel):
    approver: str
    decision: Literal["APPROVED", "REJECTED"]
    comments: str = ""


class HumanApprovalRecord(BaseModel):
    task_id: str
    approver: str
    decision: str
    comments: str
    created_at: str


class ApprovalManager:
    """Compatibility shim that refuses unsigned/caller-attributed approvals."""

    @classmethod
    def record_decision(cls, task_id: str, request: HumanApprovalRequest) -> HumanApprovalRecord:
        raise UnsignedApprovalDisabled(
            "Unsigned approval is disabled. Use a signed, PR/SHA-bound owner authorization."
        )

    @classmethod
    def has_approval(cls, task_id: str) -> bool:
        # A task id alone is not proof of an integration authorization.
        return False
