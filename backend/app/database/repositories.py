from typing import Any

from app.database import db


LOST_ITEM_FIELDS = {
    "item_name",
    "category",
    "color",
    "brand",
    "lost_at",
    "location",
    "description",
    "distinctive_features",
    "image_reference",
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



def create_match(found_item_id: int, lost_item_id: int, **fields: Any) -> int:
    return db.insert_record(
        "matches",
        {
            "found_item_id": found_item_id,
            "lost_item_id": lost_item_id,
            **fields,
        },
    )


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
