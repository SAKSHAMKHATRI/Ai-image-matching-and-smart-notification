"""Phase 13 — Claim Lifecycle & Verification Service.

Manages the claim lifecycle:
SUGGESTED → CLAIM_REQUESTED → OWNER_VERIFICATION → ADMIN_REVIEW → APPROVED / REJECTED → RETURNED

Enforces:
- Duplicate active claim prevention
- Owner and admin approval/rejection authority
- Administrative intervention & dispute escalation
- Privacy of verification details
- Transactional state transitions with full audit history
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.database import db, repositories
from app.database.claim_schemas import ClaimDecision, ClaimStatus

logger = logging.getLogger(__name__)


class ClaimServiceError(Exception):
    """Base exception for claim service errors."""


class DuplicateClaimError(ClaimServiceError):
    """Raised when an active claim already exists for the match or items."""


class UnauthorizedClaimActionError(ClaimServiceError):
    """Raised when a user attempts an unauthorized action on a claim."""


class InvalidClaimStateError(ClaimServiceError):
    """Raised when a requested transition is invalid from the current state."""


class ClaimNotFoundError(ClaimServiceError):
    """Raised when the requested claim does not exist."""


def request_claim(
    claimant_user_id: int,
    match_id: int,
    verification_notes: str | None = None,
) -> dict[str, Any]:
    """Initiate a claim request on a suggested match with optional verification notes.

    Enforces duplicate active claim prevention and logs audit event.
    """
    match_record = repositories.get_match(match_id)
    if not match_record:
        raise ClaimNotFoundError("Match not found.")

    lost_item = repositories.get_lost_item(match_record["lost_item_id"])
    found_item = repositories.get_found_item(match_record["found_item_id"])
    if not lost_item or not found_item:
        raise ClaimNotFoundError("Associated lost or found item not found.")

    # Claimant must be the lost item owner or found item reporter
    if claimant_user_id not in (lost_item["user_id"], found_item["user_id"]):
        raise UnauthorizedClaimActionError("Only the item owner or finder can initiate a claim.")

    # Check for duplicate active claim on this match
    active_match_claim = repositories.get_active_claim_for_match(match_id)
    if active_match_claim:
        raise DuplicateClaimError(
            f"An active claim (Claim #{active_match_claim['id']}) already exists for this match."
        )

    # Check if either item is already part of an active/approved claim
    active_item_claim = repositories.get_active_claim_for_items(
        lost_item["id"], found_item["id"]
    )
    if active_item_claim and active_item_claim["match_id"] != match_id:
        raise DuplicateClaimError(
            "One of the items in this match is already part of an active claim."
        )

    with db.get_connection() as connection:
        # Create claim record
        cursor = connection.execute(
            """
            INSERT INTO claims (match_id, claimant_user_id, status, verification_notes, created_at, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            RETURNING id, match_id, claimant_user_id, status, verification_notes, created_at, updated_at
            """,
            (
                match_id,
                claimant_user_id,
                ClaimStatus.CLAIM_REQUESTED.value,
                verification_notes,
            ),
        )
        claim_row = cursor.fetchone()
        claim_id = int(claim_row[0])

        # Update match status to CLAIMED
        connection.execute(
            "UPDATE matches SET status = 'CLAIMED', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (match_id,),
        )

        # Audit event
        connection.execute(
            """
            INSERT INTO audit_events (actor_user_id, entity_type, entity_id, action, details_json, created_at)
            VALUES (?, 'claims', ?, 'CLAIM_REQUESTED', ?, CURRENT_TIMESTAMP)
            """,
            (
                claimant_user_id,
                claim_id,
                json.dumps(
                    {
                        "match_id": match_id,
                        "status": ClaimStatus.CLAIM_REQUESTED.value,
                        "has_verification_notes": bool(verification_notes),
                    }
                ),
            ),
        )

    try:
        from app.services.notification_service import notify_claim_submitted

        notify_claim_submitted(
            claim_id=claim_id,
            claimant_user_id=claimant_user_id,
            lost_item=lost_item,
            found_item=found_item,
        )
    except Exception as exc:
        logger.warning("Failed to dispatch claim submitted notification: %s", exc)

    return repositories.get_claim(claim_id)  # type: ignore


def get_user_claims(user_id: int) -> list[dict[str, Any]]:
    """Get all claims involving the given user."""
    raw_claims = repositories.get_claims_by_user(user_id)
    results: list[dict[str, Any]] = []
    for c in raw_claims:
        results.append(
            {
                "id": c["id"],
                "match_id": c["match_id"],
                "claimant_user_id": c["claimant_user_id"],
                "status": c["status"],
                "verification_notes": c.get("verification_notes"),
                "found_item_id": c.get("found_item_id"),
                "lost_item_id": c.get("lost_item_id"),
                "item_name": c.get("lost_item_name", "Lost Item"),
                "category": c.get("lost_category"),
                "score": c.get("score"),
                "created_at": c["created_at"],
                "updated_at": c["updated_at"],
            }
        )
    return results


def get_claim_detail(
    claim_id: int,
    user_id: int,
    is_admin: bool = False,
) -> dict[str, Any]:
    """Retrieve full detail of a claim with role-based privacy and action permissions."""
    claim = repositories.get_claim(claim_id)
    if not claim:
        raise ClaimNotFoundError("Claim not found.")

    match_record = repositories.get_match(claim["match_id"])
    if not match_record:
        raise ClaimNotFoundError("Associated match record not found.")

    lost_item = repositories.get_lost_item(match_record["lost_item_id"])
    found_item = repositories.get_found_item(match_record["found_item_id"])
    if not lost_item or not found_item:
        raise ClaimNotFoundError("Associated item records not found.")

    is_claimant = user_id == claim["claimant_user_id"]
    is_lost_owner = user_id == lost_item["user_id"]
    is_found_finder = user_id == found_item["user_id"]

    if not (is_claimant or is_lost_owner or is_found_finder or is_admin):
        raise UnauthorizedClaimActionError("You are not authorized to view this claim.")

    # Determine user's role in this claim
    if is_admin:
        user_role = "admin"
    elif is_claimant:
        user_role = "claimant"
    elif is_lost_owner:
        user_role = "lost_owner"
    else:
        user_role = "found_finder"

    # Action permissions based on role and current status
    curr_status = claim["status"]
    is_terminal = curr_status in (
        ClaimStatus.REJECTED.value,
        ClaimStatus.RETURNED.value,
    )

    can_approve = False
    can_reject = False
    can_escalate = False
    can_return = False

    if not is_terminal:
        if is_admin:
            can_approve = curr_status != ClaimStatus.APPROVED.value
            can_reject = True
            can_escalate = True
            can_return = curr_status == ClaimStatus.APPROVED.value
        elif is_lost_owner or is_found_finder:
            # The reviewing counterparty can approve, reject, or escalate
            can_approve = curr_status not in (ClaimStatus.APPROVED.value, ClaimStatus.REJECTED.value, ClaimStatus.RETURNED.value)
            can_reject = curr_status not in (ClaimStatus.APPROVED.value, ClaimStatus.REJECTED.value, ClaimStatus.RETURNED.value)
            can_escalate = curr_status not in (ClaimStatus.APPROVED.value, ClaimStatus.REJECTED.value, ClaimStatus.RETURNED.value)
            can_return = curr_status == ClaimStatus.APPROVED.value
        elif is_claimant:
            # Claimant can escalate to admin review if needed
            can_escalate = curr_status not in (ClaimStatus.APPROVED.value, ClaimStatus.REJECTED.value, ClaimStatus.RETURNED.value)

    # Audit history
    audit_history = repositories.get_audit_events_for_entity("claims", claim_id)

    # Privacy protection: Hide raw embedding blobs and internal user IDs from safe item payloads
    safe_lost = {
        "id": lost_item["id"],
        "item_name": lost_item["item_name"],
        "category": lost_item.get("category"),
        "color": lost_item.get("color"),
        "brand": lost_item.get("brand"),
        "campus": lost_item.get("campus"),
        "lost_at": lost_item.get("lost_at"),
        "location": lost_item.get("location"),
        "description": lost_item.get("description"),
        "distinctive_features": lost_item.get("distinctive_features"),
    }
    safe_found = {
        "id": found_item["id"],
        "item_name": found_item.get("item_name"),
        "category": found_item.get("category"),
        "color": found_item.get("color"),
        "brand": found_item.get("brand"),
        "campus": found_item.get("campus"),
        "found_at": found_item.get("found_at"),
        "location": found_item.get("location"),
        "description": found_item.get("description"),
        "distinctive_features": found_item.get("distinctive_features"),
    }

    return {
        "id": claim["id"],
        "match_id": claim["match_id"],
        "claimant_user_id": claim["claimant_user_id"],
        "status": claim["status"],
        "verification_notes": claim.get("verification_notes"),
        "user_role": user_role,
        "can_approve": can_approve,
        "can_reject": can_reject,
        "can_escalate": can_escalate,
        "can_return": can_return,
        "found_item": safe_found,
        "lost_item": safe_lost,
        "match_score": match_record.get("score"),
        "audit_history": audit_history,
        "created_at": claim["created_at"],
        "updated_at": claim["updated_at"],
    }


def process_claim_decision(
    claim_id: int,
    user_id: int,
    decision: ClaimDecision | str,
    notes: str | None = None,
    is_admin: bool = False,
) -> dict[str, Any]:
    """Process an owner or admin decision (APPROVE, REJECT, or ESCALATE) on a claim."""
    claim = repositories.get_claim(claim_id)
    if not claim:
        raise ClaimNotFoundError("Claim not found.")

    match_record = repositories.get_match(claim["match_id"])
    if not match_record:
        raise ClaimNotFoundError("Associated match record not found.")

    lost_item = repositories.get_lost_item(match_record["lost_item_id"])
    found_item = repositories.get_found_item(match_record["found_item_id"])
    if not lost_item or not found_item:
        raise ClaimNotFoundError("Associated item records not found.")

    is_lost_owner = user_id == lost_item["user_id"]
    is_found_finder = user_id == found_item["user_id"]
    is_claimant = user_id == claim["claimant_user_id"]

    curr_status = claim["status"]
    if curr_status in (ClaimStatus.APPROVED.value, ClaimStatus.REJECTED.value, ClaimStatus.RETURNED.value):
        raise InvalidClaimStateError(f"Claim #{claim_id} is already in a terminal state ({curr_status}).")

    decision_val = decision.value if isinstance(decision, ClaimDecision) else str(decision).upper()

    if decision_val == ClaimDecision.APPROVE.value:
        # Only reviewing counterparty or admin can approve
        if not (is_lost_owner or is_found_finder or is_admin):
            raise UnauthorizedClaimActionError("Only the reviewing owner or administrator can approve a claim.")

        new_status = ClaimStatus.APPROVED.value
        action_name = "CLAIM_APPROVED"

    elif decision_val == ClaimDecision.REJECT.value:
        # Only reviewing counterparty or admin can reject
        if not (is_lost_owner or is_found_finder or is_admin):
            raise UnauthorizedClaimActionError("Only the reviewing owner or administrator can reject a claim.")

        new_status = ClaimStatus.REJECTED.value
        action_name = "CLAIM_REJECTED"

    elif decision_val == ClaimDecision.ESCALATE.value:
        # Claimant, owner, finder, or admin can escalate
        if not (is_claimant or is_lost_owner or is_found_finder or is_admin):
            raise UnauthorizedClaimActionError("You are not authorized to escalate this claim.")

        new_status = ClaimStatus.ADMIN_REVIEW.value
        action_name = "CLAIM_ESCALATED_ADMIN_REVIEW"

    else:
        raise ValueError(f"Unknown claim decision: {decision}")

    with db.get_connection() as connection:
        # Update claim status
        connection.execute(
            """
            UPDATE claims
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (new_status, claim_id),
        )

        # Update match status if approved/rejected
        if new_status == ClaimStatus.APPROVED.value:
            connection.execute(
                "UPDATE matches SET status = 'CLAIMED', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (claim["match_id"],),
            )
        elif new_status == ClaimStatus.REJECTED.value:
            connection.execute(
                "UPDATE matches SET status = 'REJECTED', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (claim["match_id"],),
            )

        # Record audit event
        connection.execute(
            """
            INSERT INTO audit_events (actor_user_id, entity_type, entity_id, action, details_json, created_at)
            VALUES (?, 'claims', ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (
                user_id,
                claim_id,
                action_name,
                json.dumps(
                    {
                        "previous_status": curr_status,
                        "new_status": new_status,
                        "notes": notes,
                        "decision": decision_val,
                    }
                ),
            ),
        )

    try:
        from app.services.notification_service import notify_claim_status_change

        notify_claim_status_change(
            claim_id=claim_id,
            new_status=new_status,
            claimant_user_id=claim["claimant_user_id"],
        )
    except Exception as exc:
        logger.warning("Failed to dispatch claim decision notification: %s", exc)

    return get_claim_detail(claim_id, user_id, is_admin)


def process_item_return(
    claim_id: int,
    user_id: int,
    handover_notes: str | None = None,
    handover_location: str | None = None,
    is_admin: bool = False,
) -> dict[str, Any]:
    """Execute item handover / return and close the claim lifecycle.

    Enforces:
    - Claim must exist.
    - User must be authorized (lost item owner, found item finder, or administrator).
    - Claim must be in APPROVED status (or ADMIN_REVIEW if administrator).
    - Transactionally transitions:
        * claims.status -> RETURNED
        * matches.status -> CLAIMED
        * lost_items.status -> RETURNED
        * found_items.status -> RETURNED
    - Logs structured immutable audit events for claim, lost item, and found item.
    - Prevents closed claims from being modified without administrator intervention.
    """
    claim = repositories.get_claim(claim_id)
    if not claim:
        raise ClaimNotFoundError("Claim not found.")

    match_record = repositories.get_match(claim["match_id"])
    if not match_record:
        raise ClaimNotFoundError("Associated match record not found.")

    lost_item = repositories.get_lost_item(match_record["lost_item_id"])
    found_item = repositories.get_found_item(match_record["found_item_id"])
    if not lost_item or not found_item:
        raise ClaimNotFoundError("Associated item records not found.")

    is_lost_owner = user_id == lost_item["user_id"]
    is_found_finder = user_id == found_item["user_id"]

    if not (is_lost_owner or is_found_finder or is_admin):
        raise UnauthorizedClaimActionError(
            "Only the item owner, finder, or administrator can confirm the return."
        )

    curr_status = claim["status"]
    if curr_status == ClaimStatus.RETURNED.value:
        raise InvalidClaimStateError(f"Claim #{claim_id} has already been marked as RETURNED.")
    if curr_status == ClaimStatus.REJECTED.value:
        raise InvalidClaimStateError("Cannot process return for a rejected claim.")
    if curr_status != ClaimStatus.APPROVED.value and not is_admin:
        raise InvalidClaimStateError(
            f"Cannot complete return while claim status is {curr_status}. The claim must be APPROVED first."
        )

    with db.get_connection() as connection:
        # Update claim status
        connection.execute(
            """
            UPDATE claims
            SET status = 'RETURNED', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (claim_id,),
        )

        # Update match status
        connection.execute(
            """
            UPDATE matches
            SET status = 'CLAIMED', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (claim["match_id"],),
        )

        # Update lost item status to RETURNED
        connection.execute(
            """
            UPDATE lost_items
            SET status = 'RETURNED', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (lost_item["id"],),
        )

        # Update found item status to RETURNED
        connection.execute(
            """
            UPDATE found_items
            SET status = 'RETURNED', updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (found_item["id"],),
        )

        # Record audit event for claim
        connection.execute(
            """
            INSERT INTO audit_events (actor_user_id, entity_type, entity_id, action, details_json, created_at)
            VALUES (?, 'claims', ?, 'ITEM_RETURNED', ?, CURRENT_TIMESTAMP)
            """,
            (
                user_id,
                claim_id,
                json.dumps(
                    {
                        "previous_status": curr_status,
                        "new_status": ClaimStatus.RETURNED.value,
                        "handover_notes": handover_notes,
                        "handover_location": handover_location,
                        "lost_item_id": lost_item["id"],
                        "found_item_id": found_item["id"],
                    }
                ),
            ),
        )

        # Record audit event for lost item
        connection.execute(
            """
            INSERT INTO audit_events (actor_user_id, entity_type, entity_id, action, details_json, created_at)
            VALUES (?, 'lost_items', ?, 'STATUS_CHANGED_RETURNED', ?, CURRENT_TIMESTAMP)
            """,
            (
                user_id,
                lost_item["id"],
                json.dumps(
                    {
                        "claim_id": claim_id,
                        "previous_status": lost_item["status"],
                        "new_status": "RETURNED",
                        "handover_notes": handover_notes,
                        "handover_location": handover_location,
                    }
                ),
            ),
        )

        # Record audit event for found item
        connection.execute(
            """
            INSERT INTO audit_events (actor_user_id, entity_type, entity_id, action, details_json, created_at)
            VALUES (?, 'found_items', ?, 'STATUS_CHANGED_RETURNED', ?, CURRENT_TIMESTAMP)
            """,
            (
                user_id,
                found_item["id"],
                json.dumps(
                    {
                        "claim_id": claim_id,
                        "previous_status": found_item["status"],
                        "new_status": "RETURNED",
                        "handover_notes": handover_notes,
                        "handover_location": handover_location,
                    }
                ),
            ),
        )

    try:
        from app.services.notification_service import notify_claim_status_change

        notify_claim_status_change(
            claim_id=claim_id,
            new_status="RETURNED",
            claimant_user_id=claim["claimant_user_id"],
        )
    except Exception as exc:
        logger.warning("Failed to dispatch claim return notification: %s", exc)

    return get_claim_detail(claim_id, user_id, is_admin)


def admin_override_claim(
    claim_id: int,
    admin_user_id: int,
    new_status: ClaimStatus | str,
    admin_notes: str | None = None,
) -> dict[str, Any]:
    """Administrator intervention to update a claim's status with audit log."""
    claim = repositories.get_claim(claim_id)
    if not claim:
        raise ClaimNotFoundError("Claim not found.")

    match_record = repositories.get_match(claim["match_id"])
    lost_item = repositories.get_lost_item(match_record["lost_item_id"]) if match_record else None
    found_item = repositories.get_found_item(match_record["found_item_id"]) if match_record else None

    status_str = new_status.value if isinstance(new_status, ClaimStatus) else str(new_status).upper()
    valid_statuses = {s.value for s in ClaimStatus}
    if status_str not in valid_statuses:
        raise ValueError(f"Invalid status: {status_str}")

    curr_status = claim["status"]

    with db.get_connection() as connection:
        connection.execute(
            """
            UPDATE claims
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status_str, claim_id),
        )

        if status_str == ClaimStatus.APPROVED.value:
            connection.execute(
                "UPDATE matches SET status = 'CLAIMED', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (claim["match_id"],),
            )
        elif status_str == ClaimStatus.REJECTED.value:
            connection.execute(
                "UPDATE matches SET status = 'REJECTED', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (claim["match_id"],),
            )
        elif status_str == ClaimStatus.RETURNED.value:
            connection.execute(
                "UPDATE matches SET status = 'CLAIMED', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (claim["match_id"],),
            )
            if lost_item:
                connection.execute(
                    "UPDATE lost_items SET status = 'RETURNED', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (lost_item["id"],),
                )
            if found_item:
                connection.execute(
                    "UPDATE found_items SET status = 'RETURNED', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (found_item["id"],),
                )

        # If transitioning AWAY from RETURNED to something active/under review, restore items to ACTIVE / REPORTED
        if curr_status == ClaimStatus.RETURNED.value and status_str != ClaimStatus.RETURNED.value:
            if lost_item:
                connection.execute(
                    "UPDATE lost_items SET status = 'ACTIVE', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (lost_item["id"],),
                )
            if found_item:
                connection.execute(
                    "UPDATE found_items SET status = 'REPORTED', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (found_item["id"],),
                )

        connection.execute(
            """
            INSERT INTO audit_events (actor_user_id, entity_type, entity_id, action, details_json, created_at)
            VALUES (?, 'claims', ?, 'ADMIN_INTERVENTION', ?, CURRENT_TIMESTAMP)
            """,
            (
                admin_user_id,
                claim_id,
                json.dumps(
                    {
                        "previous_status": curr_status,
                        "new_status": status_str,
                        "admin_notes": admin_notes,
                    }
                ),
            ),
        )

    try:
        from app.services.notification_service import notify_claim_status_change

        notify_claim_status_change(
            claim_id=claim_id,
            new_status=status_str,
            claimant_user_id=claim["claimant_user_id"],
        )
    except Exception as exc:
        logger.warning("Failed to dispatch admin claim status notification: %s", exc)

    return get_claim_detail(claim_id, admin_user_id, is_admin=True)

