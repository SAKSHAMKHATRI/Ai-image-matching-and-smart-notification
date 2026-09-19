from typing import Any

from app.database import db


def create_lost_item(user_id: int, item_name: str, **fields: Any) -> int:
    return db.insert_record(
        "lost_items",
        {"user_id": user_id, "item_name": item_name, **fields},
    )


def create_found_item(user_id: int, **fields: Any) -> int:
    return db.insert_record("found_items", {"user_id": user_id, **fields})


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
