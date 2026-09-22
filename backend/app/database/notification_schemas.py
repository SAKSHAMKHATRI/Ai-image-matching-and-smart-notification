"""Pydantic schemas for Phase 17 Notifications."""

from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    type: str
    title: str
    message: str
    entity_type: str | None = None
    entity_id: int | None = None
    is_read: bool = False
    email_status: str | None = "SKIPPED"
    email_recipient: str | None = None
    email_error: str | None = None
    created_at: str


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]
    unread_count: int
    total: int
