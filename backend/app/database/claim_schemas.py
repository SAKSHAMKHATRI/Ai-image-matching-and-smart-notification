"""Pydantic schemas for Phase 13 Claims & Verification workflow."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ClaimStatus(str, Enum):
    """Lifecycle states for claims."""

    SUGGESTED = "SUGGESTED"
    CLAIM_REQUESTED = "CLAIM_REQUESTED"
    OWNER_VERIFICATION = "OWNER_VERIFICATION"
    ADMIN_REVIEW = "ADMIN_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RETURNED = "RETURNED"


class ClaimDecision(str, Enum):
    """Decision actions taken by owner or admin on a claim."""

    APPROVE = "APPROVE"
    REJECT = "REJECT"
    ESCALATE = "ESCALATE"


class CreateClaimRequest(BaseModel):
    """Request body for creating a claim on a suggested match."""

    match_id: int
    claim_explanation: str | None = Field(
        default=None,
        max_length=2000,
        description="Explanation of why claimant believes this item is theirs.",
    )
    verification_notes: str | None = Field(
        default=None,
        max_length=2000,
        description="Private proof/verification details provided by claimant.",
    )


class ClaimDecisionRequest(BaseModel):
    """Request body for approving, rejecting, or escalating a claim."""

    decision: ClaimDecision
    notes: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional notes explaining the decision or reason for escalation.",
    )


class AdminInterventionRequest(BaseModel):
    """Request body for administrator overriding a claim status."""

    new_status: ClaimStatus
    admin_notes: str | None = Field(
        default=None,
        max_length=1000,
        description="Administrative moderation notes for the audit log.",
    )


class ProcessReturnRequest(BaseModel):
    """Request body for processing item return and claim closure."""

    handover_notes: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional staff / student handover verification notes.",
    )
    handover_location: str | None = Field(
        default=None,
        max_length=200,
        description="Location/desk where the physical handover took place.",
    )


class AuditEventResponse(BaseModel):
    """Audit event record for claim actions."""

    id: int
    actor_user_id: int | None = None
    action: str
    details: dict[str, Any] | None = None
    created_at: str


class ClaimSummaryResponse(BaseModel):
    """Summary of a claim record."""

    id: int
    match_id: int
    claimant_user_id: int
    claimant_name: str | None = None
    status: str
    verification_notes: str | None = None
    found_item_id: int
    lost_item_id: int
    item_name: str
    found_item_name: str | None = None
    lost_item_name: str | None = None
    is_finder: bool | None = None
    category: str | None = None
    score: float | None = None
    created_at: str
    updated_at: str


class ClaimDetailResponse(BaseModel):
    """Full detail of a claim with associated items and audit history."""

    id: int
    match_id: int
    claimant_user_id: int
    claimant_name: str | None = None
    finder_name: str | None = None
    status: str
    verification_notes: str | None = None
    user_role: str  # "claimant", "lost_owner", "found_finder", or "admin"
    can_approve: bool
    can_reject: bool
    can_escalate: bool
    can_return: bool = False
    found_item: dict[str, Any]
    lost_item: dict[str, Any]
    match_score: float | None = None
    audit_history: list[dict[str, Any]] = []
    created_at: str
    updated_at: str

