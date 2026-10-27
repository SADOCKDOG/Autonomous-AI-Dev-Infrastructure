"""Esquemas tipados del tablero Kanban."""

from enum import Enum
from typing import Any
from datetime import datetime
from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    BACKLOG = "BACKLOG"
    READY = "READY"
    PLANNING = "PLANNING"
    IN_PROGRESS = "IN_PROGRESS"
    TESTING = "TESTING"
    REVIEW = "REVIEW"
    DONE = "DONE"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DataClassification(str, Enum):
    LOCAL_ONLY = "local_only"
    APPROVED_REMOTE = "approved_remote"
    RESTRICTED = "restricted"
    PROJECT_CONTEXT = "project_context"
    APPROVED_CODE_CONTEXT = "approved_code_context"
    APPROVED_DIFF = "approved_diff"

    @classmethod
    def _missing_(cls, value):
        val_str = str(value).lower()
        if "restrict" in val_str:
            return cls.RESTRICTED
        if "local" in val_str:
            return cls.LOCAL_ONLY
        return cls.APPROVED_REMOTE


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(default="")
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM)
    data_classification: DataClassification = Field(default=DataClassification.APPROVED_REMOTE)
    acceptance_criteria: list[str] = Field(default_factory=list)
    target_repo: str | None = Field(default=None)


class TaskTransitionRequest(BaseModel):
    target_status: TaskStatus
    agent_role: str | None = None
    reason: str = Field(default="")
    metadata: dict[str, Any] = Field(default_factory=dict)


class TaskResponse(BaseModel):
    id: str
    title: str
    description: str
    status: TaskStatus
    priority: TaskPriority
    data_classification: DataClassification
    acceptance_criteria: list[str]
    assigned_agent: str | None
    branch_name: str | None
    worktree_path: str | None
    target_repo: str | None = None
    created_at: str
    updated_at: str
