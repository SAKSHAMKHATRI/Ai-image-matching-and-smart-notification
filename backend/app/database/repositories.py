import re
from typing import Any

from app.database import db


LOST_ITEM_FIELDS = {
    "item_name",
    "category",
    "color",
    "brand",
    "campus",
    "lost_at",
    "location",
    "description",
    "distinctive_features",
    "image_reference",
    "description_embedding_blob",
    "image_embedding_blob",
}

FOUND_ITEM_FIELDS = {
    "campus",
    "found_at",
    "location",
    "item_name",
    "category",
    "color",
    "brand",
    "description",
    "distinctive_features",
    "image_reference",
    "ai_attributes_json",
    "image_embedding_blob",
    "analysis_status",
    "analysis_error",
    "analysis_requested_at",
    "analysis_completed_at",
    "status",
}



def create_lost_item(user_id: int, item_name: str, **fields: Any) -> int:
    return db.insert_record(
        "lost_items",
        {"user_id": user_id, "item_name": item_name, **fields},
    )


def list_lost_items_for_user(user_id: int) -> list[dict[str, Any]]:
    with db.get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM lost_items WHERE user_id = ? ORDER BY created_at DESC, id DESC",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_lost_item_for_user(user_id: int, item_id: int) -> dict[str, Any] | None:
    item = get_lost_item(item_id)
    if item is None or item["user_id"] != user_id:
        return None
    return item


def update_lost_item_for_user(
    user_id: int,
    item_id: int,
    fields: dict[str, Any],
) -> dict[str, Any] | None:
    unknown_fields = set(fields) - LOST_ITEM_FIELDS
    if unknown_fields:
        raise ValueError("Unsupported lost-item fields.")
    assignments = ", ".join(f"{field} = ?" for field in fields)
    values = (*fields.values(), item_id, user_id)
    with db.get_connection() as connection:
        cursor = connection.execute(
            f"""
            UPDATE lost_items
            SET {assignments}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            values,
        )
        if cursor.rowcount == 0:
            return None
    return get_lost_item_for_user(user_id, item_id)


def delete_lost_item_for_user(user_id: int, item_id: int) -> bool:
    with db.get_connection() as connection:
        item = connection.execute(
            "SELECT id FROM lost_items WHERE id = ? AND user_id = ?",
            (item_id, user_id),
        ).fetchone()
        if not item:
            return False

        # Clean up dependent claims referencing matches for this lost item
        connection.execute(
            """
            DELETE FROM claims
            WHERE match_id IN (SELECT id FROM matches WHERE lost_item_id = ?)
            """,
            (item_id,),
        )
        # Clean up matches referencing this lost item
        connection.execute(
            "DELETE FROM matches WHERE lost_item_id = ?",
            (item_id,),
        )
        # Clean up audit events for this lost item
        connection.execute(
            "DELETE FROM audit_events WHERE entity_type = 'lost_items' AND entity_id = ?",
            (item_id,),
        )
        cursor = connection.execute(
            "DELETE FROM lost_items WHERE id = ? AND user_id = ?",
            (item_id, user_id),
        )
    return cursor.rowcount == 1


def create_found_item(user_id: int, **fields: Any) -> int:
    return db.insert_record("found_items", {"user_id": user_id, **fields})


def list_found_items_for_user(user_id: int) -> list[dict[str, Any]]:
    with db.get_connection() as connection:
        rows = connection.execute(
            "SELECT * FROM found_items WHERE user_id = ? ORDER BY created_at DESC, id DESC",
            (user_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_found_item_for_user(user_id: int, item_id: int) -> dict[str, Any] | None:
    item = get_found_item(item_id)
    if item is None or item["user_id"] != user_id:
        return None
    return item


def update_found_item_for_user(
    user_id: int,
    item_id: int,
    fields: dict[str, Any],
) -> dict[str, Any] | None:
    unknown_fields = set(fields) - FOUND_ITEM_FIELDS
    if unknown_fields:
        raise ValueError("Unsupported found-item fields.")
    assignments = ", ".join(f"{field} = ?" for field in fields)
    values = (*fields.values(), item_id, user_id)
    with db.get_connection() as connection:
        cursor = connection.execute(
            f"""
            UPDATE found_items
            SET {assignments}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND user_id = ?
            """,
            values,
        )
        if cursor.rowcount == 0:
            return None
    return get_found_item_for_user(user_id, item_id)


def delete_found_item_for_user(user_id: int, item_id: int) -> bool:
    with db.get_connection() as connection:
        item = connection.execute(
            "SELECT id FROM found_items WHERE id = ? AND user_id = ?",
            (item_id, user_id),
        ).fetchone()
        if not item:
            return False

        # Clean up dependent claims referencing matches for this found item
        connection.execute(
            """
            DELETE FROM claims
            WHERE match_id IN (SELECT id FROM matches WHERE found_item_id = ?)
            """,
            (item_id,),
        )
        # Clean up matches referencing this found item
        connection.execute(
            "DELETE FROM matches WHERE found_item_id = ?",
            (item_id,),
        )
        # Clean up audit events for this found item
        connection.execute(
            "DELETE FROM audit_events WHERE entity_type = 'found_items' AND entity_id = ?",
            (item_id,),
        )
        cursor = connection.execute(
            "DELETE FROM found_items WHERE id = ? AND user_id = ?",
            (item_id, user_id),
        )
    return cursor.rowcount == 1



def create_match(found_item_id: int, lost_item_id: int, **fields: Any) -> int:
    return db.insert_record(
        "matches",
        {
            "found_item_id": found_item_id,
            "lost_item_id": lost_item_id,
            **fields,
        },
    )


def upsert_match(
    found_item_id: int,
    lost_item_id: int,
    score: float,
    explanation_json: str,
    status: str = "SUGGESTED",
) -> int:
    with db.get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO matches (found_item_id, lost_item_id, score, explanation_json, status, updated_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(found_item_id, lost_item_id) DO UPDATE SET
                score = excluded.score,
                explanation_json = excluded.explanation_json,
                status = excluded.status,
                updated_at = CURRENT_TIMESTAMP
            RETURNING id
            """,
            (found_item_id, lost_item_id, score, explanation_json, status),
        )
        row = cursor.fetchone()
        return int(row[0]) if row else 0


def get_matches_for_found_item(found_item_id: int) -> list[dict[str, Any]]:
    with db.get_connection() as connection:
        rows = connection.execute(
            """
            SELECT * FROM matches
            WHERE found_item_id = ?
            ORDER BY score DESC, created_at DESC
            """,
            (found_item_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_matches_for_lost_item(lost_item_id: int) -> list[dict[str, Any]]:
    with db.get_connection() as connection:
        rows = connection.execute(
            """
            SELECT * FROM matches
            WHERE lost_item_id = ?
            ORDER BY score DESC, created_at DESC
            """,
            (lost_item_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def create_claim(match_id: int, claimant_user_id: int, **fields: Any) -> int:
    return db.insert_record(
        "claims",
        {
            "match_id": match_id,
            "claimant_user_id": claimant_user_id,
            **fields,
        },
    )


def get_lost_item(item_id: int) -> dict[str, Any] | None:
    return db.get_record("lost_items", item_id)


def get_found_item(item_id: int) -> dict[str, Any] | None:
    return db.get_record("found_items", item_id)


def get_match(match_id: int) -> dict[str, Any] | None:
    return db.get_record("matches", match_id)


def get_claim(claim_id: int) -> dict[str, Any] | None:
    return db.get_record("claims", claim_id)


def get_active_claim_for_match(match_id: int) -> dict[str, Any] | None:
    """Return an existing non-terminal claim for a match (prevents duplicate active claims)."""
    with db.get_connection() as connection:
        row = connection.execute(
            """
            SELECT * FROM claims
            WHERE match_id = ? AND status NOT IN ('REJECTED', 'RETURNED')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (match_id,),
        ).fetchone()
        return dict(row) if row else None


def get_active_claim_for_items(lost_item_id: int, found_item_id: int) -> dict[str, Any] | None:
    """Check if either the lost item or found item is already in an approved/active claim."""
    with db.get_connection() as connection:
        row = connection.execute(
            """
            SELECT c.* FROM claims c
            JOIN matches m ON c.match_id = m.id
            WHERE (m.lost_item_id = ? OR m.found_item_id = ?)
              AND c.status IN ('CLAIM_REQUESTED', 'OWNER_VERIFICATION', 'ADMIN_REVIEW', 'APPROVED')
            ORDER BY c.created_at DESC
            LIMIT 1
            """,
            (lost_item_id, found_item_id),
        ).fetchone()
        return dict(row) if row else None


def get_claims_by_user(user_id: int) -> list[dict[str, Any]]:
    """Retrieve all claims associated with a user (as claimant, lost item owner, or found item reporter)."""
    with db.get_connection() as connection:
        rows = connection.execute(
            """
            SELECT DISTINCT c.*, m.found_item_id, m.lost_item_id, m.score,
                   l.item_name as lost_item_name, l.category as lost_category,
                   f.item_name as found_item_name, f.category as found_category,
                   l.user_id as lost_owner_id, f.user_id as found_finder_id
            FROM claims c
            JOIN matches m ON c.match_id = m.id
            JOIN lost_items l ON m.lost_item_id = l.id
            JOIN found_items f ON m.found_item_id = f.id
            WHERE c.claimant_user_id = ? OR l.user_id = ? OR f.user_id = ?
            ORDER BY c.created_at DESC
            """,
            (user_id, user_id, user_id),
        ).fetchall()
        return [dict(row) for row in rows]


def get_audit_events_for_entity(entity_type: str, entity_id: int) -> list[dict[str, Any]]:
    """Retrieve all audit history entries for a specific entity."""
    with db.get_connection() as connection:
        rows = connection.execute(
            """
            SELECT * FROM audit_events
            WHERE entity_type = ? AND entity_id = ?
            ORDER BY created_at ASC
            """,
            (entity_type, entity_id),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            if d.get("details_json"):
                try:
                    d["details"] = json.loads(d["details_json"])
                except Exception:
                    d["details"] = {}
            else:
                d["details"] = {}
            result.append(d)
        return result



def change_status(
    table: str,
    record_id: int,
    status: str,
    actor_user_id: int | None = None,
    details: dict[str, Any] | None = None,
) -> bool:
    return db.update_record_status(
        table,
        record_id,
        status,
        actor_user_id=actor_user_id,
        details=details,
    )


# Columns safe for candidate retrieval (excludes embedding blobs and user_id).
_CANDIDATE_SAFE_COLUMNS = (
    "id", "status", "item_name", "category", "color", "brand", "campus",
    "lost_at", "location", "description", "distinctive_features",
    "image_reference", "created_at",
)


def query_active_lost_items(
    *,
    category: str | None = None,
    campus: str | None = None,
    location_like: str | None = None,
    brand: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return ACTIVE lost items matching the given metadata filters.

    Results exclude embedding blobs and user_id for performance and privacy.
    Filters are case-insensitive and NULL-tolerant so missing optional attributes
    do not prematurely exclude valid candidate reports.
    """
    columns_sql = ", ".join(_CANDIDATE_SAFE_COLUMNS)
    conditions = ["status = 'ACTIVE'"]
    params: list[Any] = []

    if category is not None and category.strip():
        clean_cat = category.strip()
        base_cat = clean_cat.rstrip("s") if len(clean_cat) > 3 else clean_cat
        cat_words = [
            w
            for w in re.findall(r"[A-Za-z0-9]+", clean_cat)
            if len(w) > 2 and w.lower() not in {"and", "or", "the", "item", "items"}
        ]
        cat_conditions = [
            "category = ? COLLATE NOCASE",
            "category LIKE ? COLLATE NOCASE",
            "? LIKE ('%' || category || '%') COLLATE NOCASE",
        ]
        params.extend([clean_cat, f"{base_cat}%", clean_cat])
        for word in cat_words:
            stem = word.rstrip("s") if len(word) > 3 else word
            cat_conditions.append("category LIKE ? COLLATE NOCASE")
            params.append(f"%{stem}%")
        cat_conditions.append("category IS NULL OR category = ''")
        conditions.append(f"({' OR '.join(cat_conditions)})")

    if campus is not None and campus.strip():
        clean_campus = campus.strip()
        conditions.append(
            "("
            "campus = ? COLLATE NOCASE "
            "OR campus LIKE ? COLLATE NOCASE "
            "OR ? LIKE ('%' || campus || '%') COLLATE NOCASE "
            "OR campus IS NULL OR campus = ''"
            ")"
        )
        params.extend([clean_campus, f"%{clean_campus}%", clean_campus])

    if location_like is not None and location_like.strip():
        clean_loc = location_like.strip()
        conditions.append(
            "("
            "location LIKE ? COLLATE NOCASE "
            "OR ? LIKE ('%' || location || '%') COLLATE NOCASE "
            "OR location IS NULL OR location = ''"
            ")"
        )
        params.extend([f"%{clean_loc}%", clean_loc])

    if brand is not None and brand.strip():
        clean_brand = brand.strip()
        brand_conditions = [
            "brand = ? COLLATE NOCASE",
            "brand LIKE ? COLLATE NOCASE",
            "? LIKE ('%' || brand || '%') COLLATE NOCASE",
            "brand IS NULL OR brand = ''",
            "brand = 'Other' COLLATE NOCASE",
            "brand = 'Unknown' COLLATE NOCASE",
            "brand = 'Unbranded' COLLATE NOCASE",
            "? = 'Other' COLLATE NOCASE",
            "? = 'Unknown' COLLATE NOCASE",
            "? = 'Unbranded' COLLATE NOCASE",
        ]
        params.extend([clean_brand, f"%{clean_brand}%", clean_brand, clean_brand, clean_brand, clean_brand])
        conditions.append(f"({' OR '.join(brand_conditions)})")

    if date_from is not None and date_from.strip():
        conditions.append("(lost_at >= ? OR lost_at IS NULL OR lost_at = '')")
        params.append(date_from.strip())

    if date_to is not None and date_to.strip():
        conditions.append("(lost_at <= ? OR lost_at IS NULL OR lost_at = '')")
        params.append(date_to.strip())

    where_clause = " AND ".join(conditions)
    params.append(limit)

    with db.get_connection() as connection:
        rows = connection.execute(
            f"SELECT {columns_sql} FROM lost_items WHERE {where_clause} "
            f"ORDER BY created_at DESC LIMIT ?",
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def search_public_found_items(
    *,
    query: str | None = None,
    category: str | None = None,
    campus: str | None = None,
    location: str | None = None,
    color: str | None = None,
    brand: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Search reported/active found items for manual browsing.

    Excludes private finder details. Returns (items, total_count).
    """
    conditions = ["status IN ('REPORTED', 'ANALYZED')"]
    params: list[Any] = []

    if query is not None and query.strip():
        terms = [t for t in re.findall(r"[A-Za-z0-9]+", query.strip()) if len(t) > 1]
        for term in terms:
            conditions.append(
                "("
                "item_name LIKE ? COLLATE NOCASE "
                "OR description LIKE ? COLLATE NOCASE "
                "OR distinctive_features LIKE ? COLLATE NOCASE "
                "OR brand LIKE ? COLLATE NOCASE "
                "OR color LIKE ? COLLATE NOCASE "
                "OR category LIKE ? COLLATE NOCASE "
                "OR location LIKE ? COLLATE NOCASE "
                "OR campus LIKE ? COLLATE NOCASE"
                ")"
            )
            p = f"%{term}%"
            params.extend([p, p, p, p, p, p, p, p])

    if category is not None and category.strip():
        clean_cat = category.strip()
        cat_words = [
            w for w in re.findall(r"[A-Za-z0-9]+", clean_cat)
            if len(w) > 2 and w.lower() not in {"and", "or", "the", "item", "items"}
        ]
        cat_conds = ["category = ? COLLATE NOCASE", "category LIKE ? COLLATE NOCASE"]
        params.extend([clean_cat, f"%{clean_cat}%"])
        for w in cat_words:
            cat_conds.append("category LIKE ? COLLATE NOCASE")
            params.append(f"%{w.rstrip('s')}%")
        conditions.append(f"({' OR '.join(cat_conds)})")

    if campus is not None and campus.strip():
        clean_campus = campus.strip()
        conditions.append("(campus = ? COLLATE NOCASE OR campus LIKE ? COLLATE NOCASE OR location LIKE ? COLLATE NOCASE)")
        params.extend([clean_campus, f"%{clean_campus}%", f"%{clean_campus}%"])

    if location is not None and location.strip():
        conditions.append("location LIKE ? COLLATE NOCASE")
        params.append(f"%{location.strip()}%")

    if color is not None and color.strip():
        conditions.append("color LIKE ? COLLATE NOCASE")
        params.append(f"%{color.strip()}%")

    if brand is not None and brand.strip():
        clean_brand = brand.strip()
        conditions.append("(brand = ? COLLATE NOCASE OR brand LIKE ? COLLATE NOCASE)")
        params.extend([clean_brand, f"%{clean_brand}%"])

    if date_from is not None and date_from.strip():
        conditions.append("found_at >= ?")
        params.append(date_from.strip())

    if date_to is not None and date_to.strip():
        conditions.append("found_at <= ?")
        params.append(date_to.strip())

    where_clause = " AND ".join(conditions)

    with db.get_connection() as connection:
        count_row = connection.execute(
            f"SELECT COUNT(*) FROM found_items WHERE {where_clause}",
            params,
        ).fetchone()
        total_count = count_row[0] if count_row else 0

        paginated_params = list(params) + [limit, offset]
        rows = connection.execute(
            f"SELECT id, status, found_at, location, campus, item_name, category, color, brand, "
            f"description, distinctive_features, image_reference, created_at "
            f"FROM found_items WHERE {where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            paginated_params,
        ).fetchall()

    return [dict(row) for row in rows], total_count


def search_public_lost_items(
    *,
    query: str | None = None,
    category: str | None = None,
    campus: str | None = None,
    location: str | None = None,
    color: str | None = None,
    brand: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Search active lost items for manual student browsing.

    Excludes private owner information (roll number, email, phone). Returns (items, total_count).
    """
    conditions = ["status = 'ACTIVE'"]
    params: list[Any] = []

    if query is not None and query.strip():
        terms = [t for t in re.findall(r"[A-Za-z0-9]+", query.strip()) if len(t) > 1]
        for term in terms:
            conditions.append(
                "("
                "item_name LIKE ? COLLATE NOCASE "
                "OR description LIKE ? COLLATE NOCASE "
                "OR distinctive_features LIKE ? COLLATE NOCASE "
                "OR brand LIKE ? COLLATE NOCASE "
                "OR color LIKE ? COLLATE NOCASE "
                "OR category LIKE ? COLLATE NOCASE "
                "OR location LIKE ? COLLATE NOCASE "
                "OR campus LIKE ? COLLATE NOCASE"
                ")"
            )
            p = f"%{term}%"
            params.extend([p, p, p, p, p, p, p, p])

    if category is not None and category.strip():
        clean_cat = category.strip()
        cat_words = [
            w for w in re.findall(r"[A-Za-z0-9]+", clean_cat)
            if len(w) > 2 and w.lower() not in {"and", "or", "the", "item", "items"}
        ]
        cat_conds = ["category = ? COLLATE NOCASE", "category LIKE ? COLLATE NOCASE"]
        params.extend([clean_cat, f"%{clean_cat}%"])
        for w in cat_words:
            cat_conds.append("category LIKE ? COLLATE NOCASE")
            params.append(f"%{w.rstrip('s')}%")
        conditions.append(f"({' OR '.join(cat_conds)})")

    if campus is not None and campus.strip():
        clean_campus = campus.strip()
        conditions.append("(campus = ? COLLATE NOCASE OR campus LIKE ? COLLATE NOCASE OR location LIKE ? COLLATE NOCASE)")
        params.extend([clean_campus, f"%{clean_campus}%", f"%{clean_campus}%"])

    if location is not None and location.strip():
        conditions.append("location LIKE ? COLLATE NOCASE")
        params.append(f"%{location.strip()}%")

    if color is not None and color.strip():
        conditions.append("color LIKE ? COLLATE NOCASE")
        params.append(f"%{color.strip()}%")

    if brand is not None and brand.strip():
        clean_brand = brand.strip()
        conditions.append("(brand = ? COLLATE NOCASE OR brand LIKE ? COLLATE NOCASE)")
        params.extend([clean_brand, f"%{clean_brand}%"])

    if date_from is not None and date_from.strip():
        conditions.append("lost_at >= ?")
        params.append(date_from.strip())

    if date_to is not None and date_to.strip():
        conditions.append("lost_at <= ?")
        params.append(date_to.strip())

    where_clause = " AND ".join(conditions)

    with db.get_connection() as connection:
        count_row = connection.execute(
            f"SELECT COUNT(*) FROM lost_items WHERE {where_clause}",
            params,
        ).fetchone()
        total_count = count_row[0] if count_row else 0

        paginated_params = list(params) + [limit, offset]
        rows = connection.execute(
            f"SELECT id, status, lost_at, location, campus, item_name, category, color, brand, "
            f"description, distinctive_features, image_reference, created_at "
            f"FROM lost_items WHERE {where_clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            paginated_params,
        ).fetchall()

    return [dict(row) for row in rows], total_count


# --- Phase 17: Notification Repositories ---

def create_notification(
    user_id: int,
    type: str,
    title: str,
    message: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    email_status: str = "SKIPPED",
    email_recipient: str | None = None,
    email_error: str | None = None,
) -> int:
    with db.get_connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO notifications (
                user_id, type, title, message, entity_type, entity_id,
                email_status, email_recipient, email_error
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, type, title, message, entity_type, entity_id, email_status, email_recipient, email_error),
        )
        return int(cursor.lastrowid)


def notification_exists_for_entity(
    user_id: int,
    type: str,
    entity_type: str,
    entity_id: int,
) -> bool:
    with db.get_connection() as connection:
        row = connection.execute(
            """
            SELECT 1 FROM notifications
            WHERE user_id = ? AND type = ? AND entity_type = ? AND entity_id = ?
            LIMIT 1
            """,
            (user_id, type, entity_type, entity_id),
        ).fetchone()
        return row is not None


def list_notifications_for_user(
    user_id: int,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    with db.get_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, user_id, type, title, message, entity_type, entity_id, is_read,
                   email_status, email_recipient, email_error, created_at
            FROM notifications
            WHERE user_id = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, limit, offset),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "user_id": r["user_id"],
                "type": r["type"],
                "title": r["title"],
                "message": r["message"],
                "entity_type": r["entity_type"],
                "entity_id": r["entity_id"],
                "is_read": bool(r["is_read"]),
                "email_status": r["email_status"] if "email_status" in r.keys() else "SKIPPED",
                "email_recipient": r["email_recipient"] if "email_recipient" in r.keys() else None,
                "email_error": r["email_error"] if "email_error" in r.keys() else None,
                "created_at": r["created_at"],
            }
            for r in rows
        ]


def get_admin_user_ids() -> list[int]:
    with db.get_connection() as connection:
        rows = connection.execute(
            "SELECT id FROM users WHERE role = 'ADMIN' AND status = 'ACTIVE'"
        ).fetchall()
        return [int(r["id"]) for r in rows]


def count_unread_notifications_for_user(user_id: int) -> int:
    with db.get_connection() as connection:
        row = connection.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND is_read = 0",
            (user_id,),
        ).fetchone()
        return int(row[0]) if row else 0


def mark_notification_read(user_id: int, notification_id: int) -> bool:
    with db.get_connection() as connection:
        cursor = connection.execute(
            "UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?",
            (notification_id, user_id),
        )
        return cursor.rowcount > 0


def mark_all_notifications_read(user_id: int) -> int:
    with db.get_connection() as connection:
        cursor = connection.execute(
            "UPDATE notifications SET is_read = 1 WHERE user_id = ? AND is_read = 0",
            (user_id,),
        )
        return int(cursor.rowcount)
