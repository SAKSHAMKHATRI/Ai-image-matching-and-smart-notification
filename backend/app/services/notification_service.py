"""Phase 17 Notification & Email Dispatch Service.

Coordinates:
- In-app persistent notification creation (with unread status).
- Safe email delivery via SMTP (or mock transport in tests) with professional HTML templates.
- Delivery audit tracking (email_status, email_recipient, email_error).
- Strict privacy guarantees: PII, verification details, and raw AI attributes are NEVER exposed.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from app.database import db, repositories
from app.services.email_service import get_email_transport

logger = logging.getLogger(__name__)


def get_frontend_base_url() -> str:
    """Resolve the frontend URL from environment configuration."""
    from app.config import get_cors_origins

    app_url = os.getenv("FRONTEND_URL") or os.getenv("APP_URL") or os.getenv("VITE_API_BASE_URL")
    if (
        app_url
        and not app_url.startswith("http://127.0.0.1:8000")
        and not app_url.startswith("http://localhost:8000")
    ):
        return app_url.rstrip("/")

    origins = get_cors_origins()
    if origins:
        return origins[0].rstrip("/")
    return "http://localhost:5173"


def get_user_display_name(user_id: int) -> str:
    """Resolve a safe display name for a user without leaking PII."""
    try:
        user_record = db.get_user_record(user_id)
        if not user_record:
            return "Campus Student"

        if user_record.get("display_name"):
            return str(user_record["display_name"]).strip()

        firebase_uid = user_record.get("firebase_uid")
        if firebase_uid:
            profile = db.get_profile(firebase_uid)
            if profile and profile.get("full_name"):
                return str(profile["full_name"]).strip()

        return "Campus Student"
    except Exception as exc:
        logger.warning("Could not resolve display name for user %d: %s", user_id, exc)
        return "Campus Student"


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
    email_html: str | None = None,
) -> int:
    """Create in-app notification and optionally deliver safe email notification.

    Audit info is recorded alongside the notification. Email failures NEVER throw
    exceptions or prevent in-app notification creation.
    """
    email_status = "SKIPPED"
    email_recipient = None
    email_error = None

    if email_subject and (email_body or email_html):
        recipient = get_user_notification_email(user_id)
        email_recipient = recipient
        if recipient:
            try:
                transport = get_email_transport()
                result = transport.send_email(
                    to_email=recipient,
                    subject=email_subject,
                    body_text=email_body or "",
                    body_html=email_html,
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


def build_possible_match_html(
    lost_name: str,
    found_name: str,
    finder_name: str,
    found_location: str,
    found_date: str,
    score_pct: int,
    match_url: str,
) -> str:
    """Generate a responsive, professional HTML email for possible match notifications."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Possible Match Found</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f8fafc; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color: #f8fafc; padding: 32px 16px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width: 580px; background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.06); border: 1px solid #e2e8f0; overflow: hidden;" cellspacing="0" cellpadding="0">
          <!-- Header Banner -->
          <tr>
            <td style="background: linear-gradient(135deg, #0284c7 0%, #0369a1 100%); padding: 28px 32px; text-align: left;">
              <span style="background-color: rgba(255,255,255,0.2); color: #ffffff; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; padding: 4px 10px; border-radius: 999px; display: inline-block; margin-bottom: 8px;">Campus Lost &amp; Found</span>
              <h1 style="margin: 0; color: #ffffff; font-size: 22px; font-weight: 700; line-height: 1.3;">Possible Match Identified</h1>
            </td>
          </tr>
          <!-- Main Content -->
          <tr>
            <td style="padding: 32px;">
              <p style="margin: 0 0 20px 0; font-size: 15px; line-height: 1.6; color: #334155;">
                A possible match has been identified for your lost item report. Please review the candidate information below:
              </p>

              <!-- Item Details Table -->
              <table role="presentation" width="100%" style="border-collapse: collapse; margin-bottom: 24px; background-color: #f8fafc; border-radius: 8px; border: 1px solid #e2e8f0; overflow: hidden;" cellspacing="0" cellpadding="0">
                <tr>
                  <td style="padding: 12px 16px; border-bottom: 1px solid #e2e8f0; font-size: 13px; font-weight: 600; color: #64748b; width: 35%;">Lost Item:</td>
                  <td style="padding: 12px 16px; border-bottom: 1px solid #e2e8f0; font-size: 14px; font-weight: 600; color: #0f172a;">{lost_name}</td>
                </tr>
                <tr>
                  <td style="padding: 12px 16px; border-bottom: 1px solid #e2e8f0; font-size: 13px; font-weight: 600; color: #64748b;">Found Item:</td>
                  <td style="padding: 12px 16px; border-bottom: 1px solid #e2e8f0; font-size: 14px; font-weight: 600; color: #0f172a;">{found_name}</td>
                </tr>
                <tr>
                  <td style="padding: 12px 16px; border-bottom: 1px solid #e2e8f0; font-size: 13px; font-weight: 600; color: #64748b;">Found By:</td>
                  <td style="padding: 12px 16px; border-bottom: 1px solid #e2e8f0; font-size: 14px; color: #334155;">{finder_name}</td>
                </tr>
                <tr>
                  <td style="padding: 12px 16px; border-bottom: 1px solid #e2e8f0; font-size: 13px; font-weight: 600; color: #64748b;">Found Near:</td>
                  <td style="padding: 12px 16px; border-bottom: 1px solid #e2e8f0; font-size: 14px; color: #334155;">{found_location}</td>
                </tr>
                <tr>
                  <td style="padding: 12px 16px; border-bottom: 1px solid #e2e8f0; font-size: 13px; font-weight: 600; color: #64748b;">Date Found:</td>
                  <td style="padding: 12px 16px; border-bottom: 1px solid #e2e8f0; font-size: 14px; color: #334155;">{found_date}</td>
                </tr>
                <tr>
                  <td style="padding: 12px 16px; font-size: 13px; font-weight: 600; color: #64748b;">Match Score:</td>
                  <td style="padding: 12px 16px; font-size: 15px; font-weight: 700; color: #0284c7;">
                    <span style="background-color: #e0f2fe; color: #0369a1; padding: 4px 10px; border-radius: 6px;">{score_pct}%</span>
                  </td>
                </tr>
              </table>

              <!-- CTA Button -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="margin-bottom: 24px;">
                <tr>
                  <td align="center">
                    <a href="{match_url}" target="_blank" style="background-color: #0284c7; color: #ffffff; padding: 12px 28px; text-decoration: none; border-radius: 6px; font-size: 15px; font-weight: 600; display: inline-block; box-shadow: 0 2px 4px rgba(2, 132, 199, 0.25);">View Match Details</a>
                  </td>
                </tr>
              </table>

              <!-- Disclaimer -->
              <div style="background-color: #fffbeb; border-left: 4px solid #f59e0b; padding: 12px 16px; border-radius: 4px; margin-bottom: 20px;">
                <p style="margin: 0; font-size: 13px; line-height: 1.5; color: #92400e;">
                  <strong>Note:</strong> This is a candidate match generated using AI-assisted analysis and deterministic matching. Please review the details and verify ownership yourself before claiming.
                </p>
              </div>

              <p style="margin: 0; font-size: 13px; line-height: 1.5; color: #64748b;">
                If you believe this item is yours, you can submit a claim with private verification answers directly through the portal.
              </p>
            </td>
          </tr>
          <!-- Footer -->
          <tr>
            <td style="padding: 20px 32px; background-color: #f1f5f9; border-top: 1px solid #e2e8f0; text-align: center; font-size: 12px; color: #64748b;">
              Campus Lost &amp; Found · University Student Services<br>
              This is an automated campus notification. Student privacy is strictly maintained.
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


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

    # Do not notify for inactive, returned, or closed items
    if lost_item.get("status") in ("MATCHED", "RETURNED", "CLOSED") or found_item.get("status") in ("RETURNED", "CLOSED"):
        return None

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

    found_name = found_item.get("item_name") or found_item.get("category") or "Found Item"
    lost_name = lost_item.get("item_name") or "Lost Item"
    found_location = (
        found_item.get("found_location")
        or found_item.get("location")
        or found_item.get("campus")
        or "Campus Ground"
    )
    found_date = str(found_item.get("found_date") or found_item.get("found_at") or "Recently")

    finder_id = found_item.get("user_id")
    finder_name = get_user_display_name(finder_id) if finder_id else "Campus Student"

    score_pct = (
        int(round(score_result.score * 100)) if hasattr(score_result, "score") else 50
    )

    base_url = get_frontend_base_url()
    match_url = f"{base_url}?lost_item_id={lost_id}"

    in_app_title = "Possible Match Found"
    in_app_message = (
        f"A found item ('{found_name}') may match your lost report '{lost_name}'. (Match score: {score_pct}%)"
    )

    email_subject = "Possible Match Found - Campus Lost & Found"
    email_body = (
        f"Possible Match Found\n\n"
        f"A possible match has been identified for your lost item.\n\n"
        f"Lost Item: {lost_name}\n"
        f"Found Item: {found_name}\n"
        f"Found By: {finder_name}\n"
        f"Found Near: {found_location}\n"
        f"Date Found: {found_date}\n"
        f"Match Score: {score_pct}%\n\n"
        f"View Match Details: {match_url}\n\n"
        f"This is a candidate match generated using AI-assisted analysis and deterministic matching. "
        f"Please review the details and verify ownership yourself."
    )

    email_html = build_possible_match_html(
        lost_name=lost_name,
        found_name=found_name,
        finder_name=finder_name,
        found_location=found_location,
        found_date=found_date,
        score_pct=score_pct,
        match_url=match_url,
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
            email_html=email_html,
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
    """Notify owner (claimant), finder, and administrators when a claim is submitted."""
    # 1. In-app confirmation for claimant (lost owner)
    try:
        dispatch_notification(
            user_id=claimant_user_id,
            type="CLAIM_SUBMITTED",
            title="Claim Submitted",
            message="Claim submitted successfully. Your claim is under review.",
            entity_type="claim",
            entity_id=claim_id,
        )
    except Exception as exc:
        logger.warning("Failed to notify claimant %d of submission: %s", claimant_user_id, exc)

    # 2. In-app + safe email for finder
    finder_id = found_item.get("user_id")
    if finder_id and finder_id != claimant_user_id:
        try:
            dispatch_notification(
                user_id=finder_id,
                type="CLAIM_SUBMITTED",
                title="Claim Submitted",
                message="A claim has been submitted for an item you found.",
                entity_type="claim",
                entity_id=claim_id,
                email_subject="Claim Submitted - Campus Lost & Found",
                email_body=(
                    "A claim has been submitted for an item you found. "
                    "Log in to Campus Lost & Found to review the status."
                ),
            )
        except Exception as exc:
            logger.warning("Failed to notify finder %d of claim %d: %s", finder_id, claim_id, exc)

    # 3. In-app notification for admin/review system
    try:
        admin_ids = repositories.get_admin_user_ids()
        for admin_id in admin_ids:
            if admin_id != claimant_user_id:
                dispatch_notification(
                    user_id=admin_id,
                    type="CLAIM_UPDATE",
                    title="New Claim For Review",
                    message="New claim available for review.",
                    entity_type="claim",
                    entity_id=claim_id,
                )
    except Exception as exc:
        logger.warning("Failed to notify admins of claim %d: %s", claim_id, exc)


def notify_claim_status_change(
    claim_id: int,
    new_status: str,
    claimant_user_id: int,
    finder_user_id: int | None = None,
) -> None:
    """Notify claimant (and finder where applicable) of claim status change."""
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

    # Notify claimant
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
            "Failed to dispatch claim status notification for claim %d to claimant %d: %s",
            claim_id,
            claimant_user_id,
            exc,
        )

    # If approved or returned, also notify finder in-app
    if finder_user_id and finder_user_id != claimant_user_id:
        finder_msg = (
            "A claim for an item you found has been approved by the administrator."
            if status_upper == "APPROVED"
            else "Item return has been completed and the claim is closed."
            if status_upper == "RETURNED"
            else None
        )
        if finder_msg:
            try:
                dispatch_notification(
                    user_id=finder_user_id,
                    type="CLAIM_STATUS",
                    title="Claim Update",
                    message=finder_msg,
                    entity_type="claim",
                    entity_id=claim_id,
                )
            except Exception as exc:
                logger.warning("Failed to notify finder %d on status change: %s", finder_user_id, exc)
