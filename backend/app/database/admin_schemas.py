"""Pydantic schemas for Phase 15 Admin Dashboard and Moderation."""

from typing import Any

from pydantic import BaseModel, Field


class AdminOverviewStats(BaseModel):
    """Aggregate platform metrics for the administrator overview."""

    total_users: int
    active_users: int
    suspended_users: int
    total_lost_items: int
    active_lost_items: int
    returned_lost_items: int
    closed_lost_items: int
    total_found_items: int
    active_found_items: int
    returned_found_items: int
    closed_found_items: int
    total_matches: int
    suggested_matches: int
    claimed_matches: int
    total_claims: int
    active_claims: int
    disputed_claims: int  # ADMIN_REVIEW
    approved_claims: int
    returned_claims: int
    rejected_claims: int


class AdminUserSummary(BaseModel):
    """Summary of a user with linked student profile and activity counts."""

    id: int
    firebase_uid: str
    status: str
    role: str
    email: str | None = None
    full_name: str | None = None
    roll_number: str | None = None
    campus: str | None = None
    phone_number: str | None = None
    lost_count: int = 0
    found_count: int = 0
    claim_count: int = 0
    created_at: str
    updated_at: str


class AdminUserDetail(AdminUserSummary):
    """Detailed user view with their lost reports, found reports, and claims."""

    lost_items: list[dict[str, Any]] = []
    found_items: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []
    audit_history: list[dict[str, Any]] = []


class UpdateUserStatusRequest(BaseModel):
    """Request body for moderating user status."""

    status: str = Field(..., description="Target status: 'ACTIVE', 'SUSPENDED', or 'CLOSED'")
    reason: str | None = Field(None, max_length=1000, description="Moderation notes for the audit trail.")


class UpdateItemStatusRequest(BaseModel):
    """Request body for moderating lost or found report status."""

    status: str = Field(..., description="Target status (e.g. 'CLOSED', 'ACTIVE', 'RETURNED')")
    reason: str | None = Field(None, max_length=1000, description="Moderation notes for the audit trail.")


class AdminAuditLogEntry(BaseModel):
    """Structured audit log entry."""

    id: int
    actor_user_id: int | None = None
    actor_email: str | None = None
    entity_type: str
    entity_id: int
    action: str
    details: dict[str, Any] | None = None
    created_at: str
