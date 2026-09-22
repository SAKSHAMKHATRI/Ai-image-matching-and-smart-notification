"""Phase 15 — Admin Dashboard & Moderation Endpoints.

All endpoints require administrator authorization (`get_admin_user`).
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.firebase import AuthenticatedUser, get_admin_user
from app.database import db
from app.database.admin_schemas import (
    AdminAuditLogEntry,
    AdminOverviewStats,
    AdminUserDetail,
    AdminUserSummary,
    UpdateItemStatusRequest,
    UpdateUserStatusRequest,
)
from app.database.claim_schemas import (
    AdminInterventionRequest,
    ClaimDetailResponse,
)
from app.services.admin_service import (
    AdminServiceError,
    ItemNotFoundError,
    UserNotFoundError,
    get_admin_audit_logs,
    get_admin_overview_stats,
    get_all_claims_admin,
    get_all_found_items_admin,
    get_all_lost_items_admin,
    get_all_users_admin,
    get_user_detail_admin,
    moderate_found_item_status,
    moderate_lost_item_status,
    moderate_user_status,
)
from app.services.claim_service import (
    ClaimNotFoundError,
    admin_override_claim,
    get_claim_detail,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/verify")
def verify_admin_status(
    admin_user: AuthenticatedUser = Depends(get_admin_user),
) -> dict[str, Any]:
    """Verify administrator authorization for the caller."""
    return {
        "status": "ok",
        "uid": admin_user.uid,
        "email": admin_user.email,
        "role": admin_user.role,
        "is_admin": True,
    }


@router.get("/overview", response_model=AdminOverviewStats)
def get_overview(
    _admin: AuthenticatedUser = Depends(get_admin_user),
) -> dict[str, Any]:
    """Retrieve platform aggregate statistics for admin dashboard."""
    return get_admin_overview_stats()


@router.get("/users", response_model=list[AdminUserSummary])
def list_users(
    status_filter: str | None = Query(None, alias="status"),
    role_filter: str | None = Query(None, alias="role"),
    search: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _admin: AuthenticatedUser = Depends(get_admin_user),
) -> list[dict[str, Any]]:
    """List all registered platform users with profiles and report counts."""
    return get_all_users_admin(
        status=status_filter,
        role=role_filter,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.get("/users/{user_id}", response_model=AdminUserDetail)
def get_user_detail(
    user_id: int,
    _admin: AuthenticatedUser = Depends(get_admin_user),
) -> dict[str, Any]:
    """Retrieve full detail for a user including their reports and claims."""
    try:
        return get_user_detail_admin(user_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.patch("/users/{user_id}/status", response_model=AdminUserDetail)
def update_user_status_endpoint(
    user_id: int,
    request: UpdateUserStatusRequest,
    admin_user: AuthenticatedUser = Depends(get_admin_user),
) -> dict[str, Any]:
    """Moderate user status (e.g. suspend abusive accounts)."""
    admin_id = db.ensure_user(admin_user.uid)
    try:
        return moderate_user_status(
            user_id=user_id,
            admin_user_id=admin_id,
            new_status=request.status,
            reason=request.reason,
        )
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/lost-items", response_model=list[dict[str, Any]])
def list_lost_items(
    status_filter: str | None = Query(None, alias="status"),
    campus: str | None = Query(None),
    category: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _admin: AuthenticatedUser = Depends(get_admin_user),
) -> list[dict[str, Any]]:
    """List all lost item reports for administration and moderation."""
    return get_all_lost_items_admin(
        status=status_filter,
        campus=campus,
        category=category,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.patch("/lost-items/{item_id}/status", response_model=dict[str, Any])
def update_lost_item_status(
    item_id: int,
    request: UpdateItemStatusRequest,
    admin_user: AuthenticatedUser = Depends(get_admin_user),
) -> dict[str, Any]:
    """Moderate a lost report status (e.g. close spam or fraudulent reports)."""
    admin_id = db.ensure_user(admin_user.uid)
    try:
        return moderate_lost_item_status(
            item_id=item_id,
            admin_user_id=admin_id,
            new_status=request.status,
            reason=request.reason,
        )
    except ItemNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/found-items", response_model=list[dict[str, Any]])
def list_found_items(
    status_filter: str | None = Query(None, alias="status"),
    campus: str | None = Query(None),
    category: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _admin: AuthenticatedUser = Depends(get_admin_user),
) -> list[dict[str, Any]]:
    """List all found item reports for administration and moderation."""
    return get_all_found_items_admin(
        status=status_filter,
        campus=campus,
        category=category,
        search=search,
        limit=limit,
        offset=offset,
    )


@router.patch("/found-items/{item_id}/status", response_model=dict[str, Any])
def update_found_item_status(
    item_id: int,
    request: UpdateItemStatusRequest,
    admin_user: AuthenticatedUser = Depends(get_admin_user),
) -> dict[str, Any]:
    """Moderate a found report status (e.g. close spam or fraudulent reports)."""
    admin_id = db.ensure_user(admin_user.uid)
    try:
        return moderate_found_item_status(
            item_id=item_id,
            admin_user_id=admin_id,
            new_status=request.status,
            reason=request.reason,
        )
    except ItemNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/claims", response_model=list[dict[str, Any]])
def list_claims(
    status_filter: str | None = Query(None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _admin: AuthenticatedUser = Depends(get_admin_user),
) -> list[dict[str, Any]]:
    """List all claims with dispute status and metadata."""
    return get_all_claims_admin(status=status_filter, limit=limit, offset=offset)


@router.get("/disputes", response_model=list[dict[str, Any]])
def list_disputes(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _admin: AuthenticatedUser = Depends(get_admin_user),
) -> list[dict[str, Any]]:
    """List claims currently in ADMIN_REVIEW requiring mediation."""
    return get_all_claims_admin(status="ADMIN_REVIEW", limit=limit, offset=offset)


@router.get("/claims/{claim_id}", response_model=ClaimDetailResponse)
def get_claim_detail_for_admin(
    claim_id: int,
    admin_user: AuthenticatedUser = Depends(get_admin_user),
) -> dict[str, Any]:
    """Retrieve full claim details, associated items, and complete audit history."""
    admin_id = db.ensure_user(admin_user.uid)
    try:
        return get_claim_detail(claim_id, admin_id, is_admin=True)
    except ClaimNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post("/claims/{claim_id}/override", response_model=ClaimDetailResponse)
def override_claim_status(
    claim_id: int,
    request: AdminInterventionRequest,
    admin_user: AuthenticatedUser = Depends(get_admin_user),
) -> dict[str, Any]:
    """Administrator intervention to resolve claim dispute and override status."""
    admin_id = db.ensure_user(admin_user.uid)
    try:
        return admin_override_claim(
            claim_id=claim_id,
            admin_user_id=admin_id,
            new_status=request.new_status,
            admin_notes=request.admin_notes,
        )
    except ClaimNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("/audit-logs", response_model=list[AdminAuditLogEntry])
def list_audit_logs(
    entity_type: str | None = Query(None),
    action: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _admin: AuthenticatedUser = Depends(get_admin_user),
) -> list[dict[str, Any]]:
    """Query system-wide immutable audit trail."""
    return get_admin_audit_logs(
        entity_type=entity_type,
        action=action,
        limit=limit,
        offset=offset,
    )
