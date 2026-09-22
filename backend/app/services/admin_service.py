"""Phase 15 — Administrator Dashboard and Moderation Service.

Provides administrative controls for:
- Reviewing aggregate platform metrics & statistics
- Moderating users (review, suspend abusive accounts, reactivate)
- Moderating lost and found reports (close spam/fraudulent reports, review all items)
- Managing claims and resolving escalated disputes (ADMIN_REVIEW)
- Inspecting immutable system audit logs
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.database import db, repositories
from app.database.claim_schemas import ClaimStatus
from app.services.claim_service import (
    ClaimNotFoundError,
    admin_override_claim,
    get_claim_detail,
)

logger = logging.getLogger(__name__)


class AdminServiceError(Exception):
    """Base exception for admin service operations."""


class UserNotFoundError(AdminServiceError):
    """Raised when a requested user record is not found."""


class ItemNotFoundError(AdminServiceError):
    """Raised when a requested report item is not found."""


def get_admin_overview_stats() -> dict[str, int]:
    """Calculate aggregate platform statistics for admin dashboard."""
    with db.get_connection() as connection:
        # Users counts
        total_users = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        active_users = connection.execute("SELECT COUNT(*) FROM users WHERE status = 'ACTIVE'").fetchone()[0]
        suspended_users = connection.execute("SELECT COUNT(*) FROM users WHERE status = 'SUSPENDED'").fetchone()[0]

        # Lost items counts
        total_lost = connection.execute("SELECT COUNT(*) FROM lost_items").fetchone()[0]
        active_lost = connection.execute("SELECT COUNT(*) FROM lost_items WHERE status = 'ACTIVE'").fetchone()[0]
        returned_lost = connection.execute("SELECT COUNT(*) FROM lost_items WHERE status = 'RETURNED'").fetchone()[0]
        closed_lost = connection.execute("SELECT COUNT(*) FROM lost_items WHERE status = 'CLOSED'").fetchone()[0]

        # Found items counts
        total_found = connection.execute("SELECT COUNT(*) FROM found_items").fetchone()[0]
        active_found = connection.execute("SELECT COUNT(*) FROM found_items WHERE status IN ('REPORTED', 'ANALYZED')").fetchone()[0]
        returned_found = connection.execute("SELECT COUNT(*) FROM found_items WHERE status = 'RETURNED'").fetchone()[0]
        closed_found = connection.execute("SELECT COUNT(*) FROM found_items WHERE status = 'CLOSED'").fetchone()[0]

        # Matches counts
        total_matches = connection.execute("SELECT COUNT(*) FROM matches").fetchone()[0]
        suggested_matches = connection.execute("SELECT COUNT(*) FROM matches WHERE status = 'SUGGESTED'").fetchone()[0]
        claimed_matches = connection.execute("SELECT COUNT(*) FROM matches WHERE status = 'CLAIMED'").fetchone()[0]

        # Claims counts
        total_claims = connection.execute("SELECT COUNT(*) FROM claims").fetchone()[0]
        active_claims = connection.execute(
            "SELECT COUNT(*) FROM claims WHERE status IN ('CLAIM_REQUESTED', 'OWNER_VERIFICATION')"
        ).fetchone()[0]
        disputed_claims = connection.execute(
            "SELECT COUNT(*) FROM claims WHERE status = 'ADMIN_REVIEW'"
        ).fetchone()[0]
        approved_claims = connection.execute(
            "SELECT COUNT(*) FROM claims WHERE status = 'APPROVED'"
        ).fetchone()[0]
        returned_claims = connection.execute(
            "SELECT COUNT(*) FROM claims WHERE status = 'RETURNED'"
        ).fetchone()[0]
        rejected_claims = connection.execute(
            "SELECT COUNT(*) FROM claims WHERE status = 'REJECTED'"
        ).fetchone()[0]

    return {
        "total_users": int(total_users),
        "active_users": int(active_users),
        "suspended_users": int(suspended_users),
        "total_lost_items": int(total_lost),
        "active_lost_items": int(active_lost),
        "returned_lost_items": int(returned_lost),
        "closed_lost_items": int(closed_lost),
        "total_found_items": int(total_found),
        "active_found_items": int(active_found),
        "returned_found_items": int(returned_found),
        "closed_found_items": int(closed_found),
        "total_matches": int(total_matches),
        "suggested_matches": int(suggested_matches),
        "claimed_matches": int(claimed_matches),
        "total_claims": int(total_claims),
        "active_claims": int(active_claims),
        "disputed_claims": int(disputed_claims),
        "approved_claims": int(approved_claims),
        "returned_claims": int(returned_claims),
        "rejected_claims": int(rejected_claims),
    }


def get_all_users_admin(
    status: str | None = None,
    role: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List users with student profile information and report counts."""
    conditions = ["1=1"]
    params: list[Any] = []

    if status:
        conditions.append("u.status = ?")
        params.append(status.upper())

    if role:
        conditions.append("u.role = ?")
        params.append(role.upper())

    if search and search.strip():
        term = f"%{search.strip()}%"
        conditions.append(
            "(p.full_name LIKE ? OR u.display_name LIKE ? OR u.email LIKE ? OR p.university_email LIKE ? OR p.roll_number LIKE ? OR u.firebase_uid LIKE ?)"
        )
        params.extend([term, term, term, term, term, term])

    where_clause = " AND ".join(conditions)
    query = f"""
        SELECT
            u.id,
            u.firebase_uid,
            u.status,
            u.role,
            u.created_at,
            u.updated_at,
            COALESCE(p.full_name, u.display_name) AS full_name,
            COALESCE(u.email, p.university_email) AS email,
            p.roll_number,
            p.campus,
            p.phone_number,
            (SELECT COUNT(*) FROM lost_items l WHERE l.user_id = u.id) as lost_count,
            (SELECT COUNT(*) FROM found_items f WHERE f.user_id = u.id) as found_count,
            (SELECT COUNT(*) FROM claims c WHERE c.claimant_user_id = u.id) as claim_count
        FROM users u
        LEFT JOIN student_profiles p ON u.firebase_uid = p.firebase_uid
        WHERE {where_clause}
        ORDER BY u.created_at DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    with db.get_connection() as connection:
        rows = connection.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_user_detail_admin(user_id: int) -> dict[str, Any]:
    """Retrieve full admin detail for a specific user."""
    user = db.get_user_record(user_id)
    if not user:
        raise UserNotFoundError(f"User #{user_id} does not exist.")

    profile = db.get_profile(user["firebase_uid"]) or {}

    with db.get_connection() as connection:
        lost_items = [
            dict(r)
            for r in connection.execute(
                "SELECT * FROM lost_items WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        ]
        found_items = [
            dict(r)
            for r in connection.execute(
                "SELECT * FROM found_items WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        ]
        claims = [
            dict(r)
            for r in connection.execute(
                "SELECT * FROM claims WHERE claimant_user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
        ]
        audit_history = repositories.get_audit_events_for_entity("users", user_id)

    return {
        "id": user["id"],
        "firebase_uid": user["firebase_uid"],
        "status": user["status"],
        "role": user.get("role", "STUDENT"),
        "created_at": user["created_at"],
        "updated_at": user["updated_at"],
        "full_name": profile.get("full_name") or user.get("display_name"),
        "email": user.get("email") or profile.get("university_email"),
        "roll_number": profile.get("roll_number"),
        "campus": profile.get("campus"),
        "phone_number": profile.get("phone_number"),
        "lost_count": len(lost_items),
        "found_count": len(found_items),
        "claim_count": len(claims),
        "lost_items": lost_items,
        "found_items": found_items,
        "claims": claims,
        "audit_history": audit_history,
    }


def moderate_user_status(
    user_id: int,
    admin_user_id: int,
    new_status: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """Moderate user status (ACTIVE, SUSPENDED, CLOSED) and log immutable audit event."""
    user = db.get_user_record(user_id)
    if not user:
        raise UserNotFoundError(f"User #{user_id} does not exist.")

    target_status = new_status.upper()
    if target_status not in ("ACTIVE", "SUSPENDED", "CLOSED"):
        raise ValueError(f"Invalid user status: {target_status}")

    prev_status = user["status"]

    with db.get_connection() as connection:
        connection.execute(
            "UPDATE users SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (target_status, user_id),
        )
        connection.execute(
            """
            INSERT INTO audit_events (actor_user_id, entity_type, entity_id, action, details_json, created_at)
            VALUES (?, 'users', ?, 'USER_STATUS_MODERATED', ?, CURRENT_TIMESTAMP)
            """,
            (
                admin_user_id,
                user_id,
                json.dumps(
                    {
                        "previous_status": prev_status,
                        "new_status": target_status,
                        "reason": reason,
                    }
                ),
            ),
        )

    return get_user_detail_admin(user_id)


def get_all_lost_items_admin(
    status: str | None = None,
    campus: str | None = None,
    category: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List all lost items for admin moderation."""
    conditions = ["1=1"]
    params: list[Any] = []

    if status:
        conditions.append("l.status = ?")
        params.append(status.upper())

    if campus:
        conditions.append("l.campus = ? COLLATE NOCASE")
        params.append(campus)

    if category:
        conditions.append("l.category = ? COLLATE NOCASE")
        params.append(category)

    if search and search.strip():
        term = f"%{search.strip()}%"
        conditions.append("(l.item_name LIKE ? OR l.description LIKE ? OR l.brand LIKE ?)")
        params.extend([term, term, term])

    where_clause = " AND ".join(conditions)
    query = f"""
        SELECT l.*, p.full_name as owner_name, p.university_email as owner_email, p.roll_number as owner_roll
        FROM lost_items l
        JOIN users u ON l.user_id = u.id
        LEFT JOIN student_profiles p ON u.firebase_uid = p.firebase_uid
        WHERE {where_clause}
        ORDER BY l.created_at DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    with db.get_connection() as connection:
        rows = connection.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def moderate_lost_item_status(
    item_id: int,
    admin_user_id: int,
    new_status: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """Moderate lost item status (e.g. close fraudulent report)."""
    item = repositories.get_lost_item(item_id)
    if not item:
        raise ItemNotFoundError(f"Lost item #{item_id} not found.")

    target_status = new_status.upper()
    valid_statuses = {"DRAFT", "ACTIVE", "MATCHED", "RETURNED", "CLOSED"}
    if target_status not in valid_statuses:
        raise ValueError(f"Invalid status: {target_status}")

    prev_status = item["status"]

    with db.get_connection() as connection:
        connection.execute(
            "UPDATE lost_items SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (target_status, item_id),
        )
        connection.execute(
            """
            INSERT INTO audit_events (actor_user_id, entity_type, entity_id, action, details_json, created_at)
            VALUES (?, 'lost_items', ?, 'LOST_ITEM_MODERATED', ?, CURRENT_TIMESTAMP)
            """,
            (
                admin_user_id,
                item_id,
                json.dumps(
                    {
                        "previous_status": prev_status,
                        "new_status": target_status,
                        "reason": reason,
                    }
                ),
            ),
        )

    return repositories.get_lost_item(item_id)  # type: ignore


def get_all_found_items_admin(
    status: str | None = None,
    campus: str | None = None,
    category: str | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List all found items for admin moderation."""
    conditions = ["1=1"]
    params: list[Any] = []

    if status:
        conditions.append("f.status = ?")
        params.append(status.upper())

    if campus:
        conditions.append("f.campus = ? COLLATE NOCASE")
        params.append(campus)

    if category:
        conditions.append("f.category = ? COLLATE NOCASE")
        params.append(category)

    if search and search.strip():
        term = f"%{search.strip()}%"
        conditions.append("(f.item_name LIKE ? OR f.description LIKE ? OR f.brand LIKE ?)")
        params.extend([term, term, term])

    where_clause = " AND ".join(conditions)
    query = f"""
        SELECT f.*, p.full_name as finder_name, p.university_email as finder_email, p.roll_number as finder_roll
        FROM found_items f
        JOIN users u ON f.user_id = u.id
        LEFT JOIN student_profiles p ON u.firebase_uid = p.firebase_uid
        WHERE {where_clause}
        ORDER BY f.created_at DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    with db.get_connection() as connection:
        rows = connection.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def moderate_found_item_status(
    item_id: int,
    admin_user_id: int,
    new_status: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """Moderate found item status (e.g. close spam/fraudulent report)."""
    item = repositories.get_found_item(item_id)
    if not item:
        raise ItemNotFoundError(f"Found item #{item_id} not found.")

    target_status = new_status.upper()
    valid_statuses = {"REPORTED", "ANALYZING", "ANALYZED", "RETURNED", "CLOSED"}
    if target_status not in valid_statuses:
        raise ValueError(f"Invalid status: {target_status}")

    prev_status = item["status"]

    with db.get_connection() as connection:
        connection.execute(
            "UPDATE found_items SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (target_status, item_id),
        )
        connection.execute(
            """
            INSERT INTO audit_events (actor_user_id, entity_type, entity_id, action, details_json, created_at)
            VALUES (?, 'found_items', ?, 'FOUND_ITEM_MODERATED', ?, CURRENT_TIMESTAMP)
            """,
            (
                admin_user_id,
                item_id,
                json.dumps(
                    {
                        "previous_status": prev_status,
                        "new_status": target_status,
                        "reason": reason,
                    }
                ),
            ),
        )

    return repositories.get_found_item(item_id)  # type: ignore


def get_all_claims_admin(
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List all claims with rich metadata and dispute tags for admin management."""
    conditions = ["1=1"]
    params: list[Any] = []

    if status:
        conditions.append("c.status = ?")
        params.append(status.upper())

    where_clause = " AND ".join(conditions)
    query = f"""
        SELECT
            c.*,
            m.score as match_score,
            m.found_item_id,
            m.lost_item_id,
            l.item_name as lost_item_name,
            l.category as lost_category,
            f.item_name as found_item_name,
            f.category as found_category,
            p_claimant.full_name as claimant_name,
            p_claimant.university_email as claimant_email,
            p_owner.full_name as owner_name,
            p_finder.full_name as finder_name
        FROM claims c
        JOIN matches m ON c.match_id = m.id
        JOIN lost_items l ON m.lost_item_id = l.id
        JOIN found_items f ON m.found_item_id = f.id
        JOIN users u_claimant ON c.claimant_user_id = u_claimant.id
        LEFT JOIN student_profiles p_claimant ON u_claimant.firebase_uid = p_claimant.firebase_uid
        JOIN users u_owner ON l.user_id = u_owner.id
        LEFT JOIN student_profiles p_owner ON u_owner.firebase_uid = p_owner.firebase_uid
        JOIN users u_finder ON f.user_id = u_finder.id
        LEFT JOIN student_profiles p_finder ON u_finder.firebase_uid = p_finder.firebase_uid
        WHERE {where_clause}
        ORDER BY
            CASE WHEN c.status = 'ADMIN_REVIEW' THEN 0 ELSE 1 END,
            c.created_at DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    with db.get_connection() as connection:
        rows = connection.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_admin_audit_logs(
    entity_type: str | None = None,
    action: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Query system-wide structured audit history."""
    conditions = ["1=1"]
    params: list[Any] = []

    if entity_type:
        conditions.append("a.entity_type = ?")
        params.append(entity_type.lower())

    if action:
        conditions.append("a.action LIKE ?")
        params.append(f"%{action}%")

    where_clause = " AND ".join(conditions)
    query = f"""
        SELECT
            a.id,
            a.actor_user_id,
            a.entity_type,
            a.entity_id,
            a.action,
            a.details_json,
            a.created_at,
            p.university_email as actor_email
        FROM audit_events a
        LEFT JOIN users u ON a.actor_user_id = u.id
        LEFT JOIN student_profiles p ON u.firebase_uid = p.firebase_uid
        WHERE {where_clause}
        ORDER BY a.created_at DESC
        LIMIT ? OFFSET ?
    """
    params.extend([limit, offset])

    with db.get_connection() as connection:
        rows = connection.execute(query, params).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            details_raw = d.pop("details_json", None)
            d["details"] = json.loads(details_raw) if details_raw else None
            results.append(d)
        return results
