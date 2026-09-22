"""Phase 17 — Notification Endpoints for Students."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.firebase import AuthenticatedUser, get_current_user
from app.database import db, repositories
from app.database.notification_schemas import (
    NotificationListResponse,
    NotificationResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
def list_my_notifications(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Retrieve notifications for the current authenticated student."""
    user_id = db.ensure_user(current_user.uid)
    notifications = repositories.list_notifications_for_user(user_id, limit=limit, offset=offset)
    unread_count = repositories.count_unread_notifications_for_user(user_id)
    return {
        "notifications": notifications,
        "unread_count": unread_count,
        "total": len(notifications),
    }


@router.patch("/{notification_id}/read", response_model=dict[str, Any])
def mark_notification_as_read(
    notification_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Mark a specific notification as read."""
    user_id = db.ensure_user(current_user.uid)
    success = repositories.mark_notification_read(user_id, notification_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found.",
        )
    return {
        "success": True,
        "notification_id": notification_id,
        "is_read": True,
    }


@router.post("/read-all", response_model=dict[str, Any])
def mark_all_notifications_as_read(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Mark all notifications for the current student as read."""
    user_id = db.ensure_user(current_user.uid)
    updated_count = repositories.mark_all_notifications_read(user_id)
    return {
        "success": True,
        "updated_count": updated_count,
    }
