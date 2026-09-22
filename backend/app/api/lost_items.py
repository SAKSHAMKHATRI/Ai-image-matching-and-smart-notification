import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.auth.firebase import AuthenticatedUser, get_current_user
from app.database import db, repositories
from app.database.lost_item_schemas import (
    LostItemCreate,
    LostItemResponse,
    LostItemUpdate,
)
from app.services.embedding_service import get_embedding_provider, serialize_embedding
from app.services.matching_service import evaluate_and_persist_matches_for_lost_item
from app.services.storage_service import store_image, validate_and_read_image

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/lost-items", tags=["lost-items"])


def serialize_lost_item(item: dict[str, object]) -> dict[str, object]:
    return {
        "id": item["id"],
        "status": item["status"],
        "item_name": item["item_name"],
        "category": item["category"],
        "color": item["color"],
        "brand": item["brand"],
        "campus": item.get("campus"),
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
        "campus": fields.get("campus"),
        "lost_at": fields["lost_date"].isoformat() if hasattr(fields["lost_date"], "isoformat") else fields["lost_date"],
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
    db_fields = profile_fields_to_database(report.model_dump())

    # Generate description embedding if description text is present
    desc_text = report.description or report.item_name
    if desc_text and desc_text.strip():
        try:
            provider = get_embedding_provider()
            emb_res = provider.embed_text(desc_text)
            if emb_res.status == "SUCCESS":
                db_fields["description_embedding_blob"] = serialize_embedding(emb_res.vector)
        except Exception as exc:
            logger.warning("Failed to generate description embedding for lost item: %s", exc)

    item_id = repositories.create_lost_item(user_id, **db_fields)
    item = repositories.get_lost_item_for_user(user_id, item_id)
    if item:
        try:
            evaluate_and_persist_matches_for_lost_item(item)
        except Exception as exc:
            logger.warning("Automatic match evaluation for lost item %d failed: %s", item_id, exc)
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
    db_fields = profile_fields_to_database(report.model_dump())
    desc_text = report.description or report.item_name
    if desc_text and desc_text.strip():
        try:
            provider = get_embedding_provider()
            emb_res = provider.embed_text(desc_text)
            if emb_res.status == "SUCCESS":
                db_fields["description_embedding_blob"] = serialize_embedding(emb_res.vector)
        except Exception as exc:
            logger.warning("Failed to regenerate description embedding on lost item update: %s", exc)
    item = repositories.update_lost_item_for_user(
        user_id,
        item_id,
        db_fields,
    )
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lost item not found.")
    try:
        evaluate_and_persist_matches_for_lost_item(item)
    except Exception as exc:
        logger.warning("Automatic match evaluation for updated lost item %d failed: %s", item_id, exc)
    return serialize_lost_item(item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_lost_item(
    item_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> None:
    if not repositories.delete_lost_item_for_user(current_user_id(current_user), item_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lost item not found.")


@router.post("/{item_id}/image", response_model=LostItemResponse)
async def upload_lost_item_image(
    item_id: int,
    image: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, object]:
    user_id = current_user_id(current_user)
    item = repositories.get_lost_item_for_user(user_id, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lost item not found.")

    contents, content_type = await validate_and_read_image(image)
    try:
        stored_image = store_image(contents, content_type, current_user.uid, item_id)
    except Exception as exc:
        logger.exception("Failed to store lost-item image for item_id=%d: %s", item_id, exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Image storage is temporarily unavailable.",
        ) from exc

    updated_item = repositories.update_lost_item_for_user(
        user_id,
        item_id,
        {"image_reference": stored_image.path},
    )
    if updated_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lost item not found.")
    return serialize_lost_item(updated_item)
