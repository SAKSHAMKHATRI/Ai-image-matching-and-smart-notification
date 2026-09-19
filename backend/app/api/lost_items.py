from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.firebase import AuthenticatedUser, get_current_user
from app.database import db, repositories
from app.database.lost_item_schemas import (
    LostItemCreate,
    LostItemResponse,
    LostItemUpdate,
)

router = APIRouter(prefix="/api/lost-items", tags=["lost-items"])


def serialize_lost_item(item: dict[str, object]) -> dict[str, object]:
    return {
        "id": item["id"],
        "status": item["status"],
        "item_name": item["item_name"],
        "category": item["category"],
        "color": item["color"],
        "brand": item["brand"],
        "lost_date": item["lost_at"],
        "approximate_location": item["location"],
        "description": item["description"],
        "distinctive_features": item["distinctive_features"],
        "image_reference": item["image_reference"],
        "created_at": item["created_at"],
        "updated_at": item["updated_at"],
    }


def profile_fields_to_database(fields: dict[str, object]) -> dict[str, object]:
    return {
        "item_name": fields["item_name"],
        "category": fields["category"],
        "color": fields["color"],
        "brand": fields["brand"],
        "lost_at": fields["lost_date"].isoformat(),  # type: ignore[union-attr]
        "location": fields["approximate_location"],
        "description": fields["description"],
        "distinctive_features": fields["distinctive_features"],
        "image_reference": fields["image_reference"],
    }


def current_user_id(current_user: AuthenticatedUser) -> int:
    return db.ensure_user(current_user.uid)


@router.post("", response_model=LostItemResponse, status_code=status.HTTP_201_CREATED)
def create_lost_item(
    report: LostItemCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, object]:
    user_id = current_user_id(current_user)
    item_id = repositories.create_lost_item(
        user_id,
        **profile_fields_to_database(report.model_dump()),
    )
    item = repositories.get_lost_item_for_user(user_id, item_id)
    return serialize_lost_item(item)  # type: ignore[arg-type]


@router.get("", response_model=list[LostItemResponse])
def list_my_lost_items(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> list[dict[str, object]]:
    user_id = current_user_id(current_user)
    return [serialize_lost_item(item) for item in repositories.list_lost_items_for_user(user_id)]


@router.get("/{item_id}", response_model=LostItemResponse)
def get_my_lost_item(
    item_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, object]:
    item = repositories.get_lost_item_for_user(current_user_id(current_user), item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lost item not found.")
    return serialize_lost_item(item)


@router.patch("/{item_id}", response_model=LostItemResponse)
def update_my_lost_item(
    item_id: int,
    report: LostItemUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, object]:
    user_id = current_user_id(current_user)
    item = repositories.update_lost_item_for_user(
        user_id,
        item_id,
        profile_fields_to_database(report.model_dump()),
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lost item not found.")
    return serialize_lost_item(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_lost_item(
    item_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> None:
    if not repositories.delete_lost_item_for_user(current_user_id(current_user), item_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lost item not found.")
