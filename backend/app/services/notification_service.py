"""Phase 17 Notification & Email Dispatch Service.

Coordinates:
- In-app persistent notification creation (with unread status).
- Safe email delivery via SMTP (or mock transport in tests).
- Delivery audit tracking (email_status, email_recipient, email_error).
- Strict privacy guarantees: PII, verification details, and raw AI attributes are NEVER exposed.
"""

from __future__ import annotations

import logging
from typing import Any

from app.database import db, repositories
from app.services.email_service import get_email_transport

logger = logging.getLogger(__name__)


def get_user_notification_email(user_id: int) -> str | None:
    """Resolve the university or account email address for a given user ID."""
    try:
        user_record = db.get_user_record(user_id)
        if not user_record:
            return None

        # 1. Direct email field on users table
        email = user_record.get("email")
        if email and isinstance(email, str) and "@" in email:
            return email.strip()

        # 2. Check student profile
        firebase_uid = user_record.get("firebase_uid")
        if firebase_uid:
            profile = db.get_profile(firebase_uid)
            if profile and profile.get("university_email"):
                u_email = str(profile["university_email"]).strip()
                if "@" in u_email:
                    return u_email

        return None
    except Exception as exc:
        logger.warning("Could not resolve email for user_id %d: %s", user_id, exc)
        return None


def dispatch_notification(
    user_id: int,
    type: str,
    title: str,
    message: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    email_subject: str | None = None,
    email_body: str | None = None,
) -> int:
    """Create in-app notification and optionally deliver safe email notification.

    Audit info is recorded alongside the notification. Email failures NEVER throw
    exceptions or prevent in-app notification creation.
    """
    email_status = "SKIPPED"
    email_recipient = None
    email_error = None

    if email_subject and email_body:
        recipient = get_user_notification_email(user_id)
        email_recipient = recipient
        if recipient:
            try:
                transport = get_email_transport()
                result = transport.send_email(
                    to_email=recipient,
                    subject=email_subject,
                    body_text=email_body,
                )
                email_status = result.status
                email_error = result.error
            except Exception as exc:
                email_status = "FAILED"
                email_error = str(exc)
                logger.error(
                    "Unexpected error dispatching email to %s for user %d: %s",
                    recipient,
                    user_id,
                    exc,
                )
        else:
            email_status = "SKIPPED"
            email_error = "No verified email address found for user."

    notif_id = repositories.create_notification(
        user_id=user_id,
        type=type,
        title=title,
        message=message,
        entity_type=entity_type,
        entity_id=entity_id,
        email_status=email_status,
        email_recipient=email_recipient,
        email_error=email_error,
    )
    return notif_id


def notify_possible_match(
    lost_item: dict[str, Any],
    found_item: dict[str, Any],
    score_result: Any,
) -> int | None:
    """Notify the lost item owner of a possible match via in-app alert and safe email."""
    lost_owner_id = lost_item.get("user_id")
    if not lost_owner_id:
        return None
    lost_id = lost_item["id"]

    # Only notify on eligible matches (score >= 0.30 or not low confidence)
    from app.services.scoring_service import MatchClassification

    if (
        hasattr(score_result, "score")
        and score_result.score < 0.30
        and getattr(score_result, "classification", None) == MatchClassification.LOW_CONFIDENCE
    ):
        return None

    # Deduplicate: do not create redundant notifications for the same lost item match
    if repositories.notification_exists_for_entity(
        user_id=lost_owner_id,
        type="POSSIBLE_MATCH",
        entity_type="lost_item",
        entity_id=lost_id,
    ):
        return None

    found_name = found_item.get("item_name") or found_item.get("category") or "an item"
    lost_name = lost_item.get("item_name") or "your lost report"
    score_pct = (
        int(round(score_result.score * 100)) if hasattr(score_result, "score") else 50
    )

    in_app_title = "Possible Match Found"
    in_app_message = (
        f"A found item ('{found_name}') may match your lost report '{lost_name}'. (Match score: {score_pct}%)"
    )

    email_subject = "Possible Match Found - Campus Lost & Found"
    email_body = (
        "A possible match has been identified for one of your lost-item reports. "
        "Log in to Campus Lost & Found to review the match details."
    )

    try:
        return dispatch_notification(
            user_id=lost_owner_id,
            type="POSSIBLE_MATCH",
            title=in_app_title,
            message=in_app_message,
            entity_type="lost_item",
            entity_id=lost_id,
            email_subject=email_subject,
            email_body=email_body,
        )
    except Exception as exc:
        logger.warning(
            "Failed to dispatch possible match notification for user %d: %s",
            lost_owner_id,
            exc,
        )
        return None


def notify_claim_submitted(
    claim_id: int,
    claimant_user_id: int,
    lost_item: dict[str, Any],
    found_item: dict[str, Any],
) -> None:
    """Notify the relevant counterparty and system administrators when a claim is filed."""
    # Determine the counterparty (owner or finder) who didn't file the claim
    counterparty_id = (
        found_item["user_id"]
        if claimant_user_id == lost_item["user_id"]
        else lost_item["user_id"]
    )

    # 1. Notify counterparty in-app + safe email
    if counterparty_id and counterparty_id != claimant_user_id:
        try:
            dispatch_notification(
                user_id=counterparty_id,
                type="CLAIM_SUBMITTED",
                title="Claim Submitted",
                message="Someone submitted a claim related to one of your possible matches. Please log in to review it.",
                entity_type="claim",
                entity_id=claim_id,
                email_subject="Claim Submitted - Campus Lost & Found",
                email_body="Someone submitted a claim related to one of your possible matches. Please log in to review it.",
            )
        except Exception as exc:
            logger.warning(
                "Failed to notify counterparty %d on claim %d: %s",
                counterparty_id,
                claim_id,
                exc,
            )

    # 2. In-app notification for admin/review system
    try:
        admin_ids = repositories.get_admin_user_ids()
        for admin_id in admin_ids:
            if admin_id != claimant_user_id:
                dispatch_notification(
                    user_id=admin_id,
                    type="CLAIM_UPDATE",
                    title="New Claim For Review",
                    message=f"A new claim (Claim #{claim_id}) has been submitted and is awaiting review.",
                    entity_type="claim",
                    entity_id=claim_id,
                    email_subject=None,
                    email_body=None,
                )
    except Exception as exc:
        logger.warning("Failed to notify admins of claim %d: %s", claim_id, exc)


def notify_claim_status_change(
    claim_id: int,
    new_status: str,
    claimant_user_id: int,
) -> None:
    """Notify claimant of claim status change (APPROVED, REJECTED, RETURNED, ADMIN_REVIEW, etc.)."""
    status_upper = str(new_status).upper()

    if status_upper == "APPROVED":
        email_subject = "Claim Approved - Campus Lost & Found"
        msg = "Your claim has been approved. Log in to Campus Lost & Found to review the next steps."
        title = "Claim Approved"
    elif status_upper == "REJECTED":
        email_subject = "Claim Status Update - Campus Lost & Found"
        msg = "Your claim status has been updated. Log in to Campus Lost & Found to review the details."
        title = "Claim Status Update"
    elif status_upper == "RETURNED":
        email_subject = "Item Return Completed - Campus Lost & Found"
        msg = "Your lost/found case has progressed to the return stage. Log in to review the status."
        title = "Item Return Completed"
    elif status_upper in ("OWNER_VERIFICATION", "ADMIN_REVIEW"):
        email_subject = "Claim Under Review - Campus Lost & Found"
        msg = "Your claim has progressed to verification/review. Log in to Campus Lost & Found to review the status."
        title = "Claim Under Review"
    else:
        email_subject = "Claim Status Update - Campus Lost & Found"
        msg = f"Your claim status has been updated to {status_upper}. Log in to review the details."
        title = "Claim Status Update"

    try:
        dispatch_notification(
            user_id=claimant_user_id,
            type="CLAIM_STATUS",
            title=title,
            message=msg,
            entity_type="claim",
            entity_id=claim_id,
            email_subject=email_subject,
            email_body=msg,
        )
    except Exception as exc:
        logger.warning(
            "Failed to dispatch claim status notification for claim %d to user %d: %s",
            claim_id,
            claimant_user_id,
            exc,
        )
