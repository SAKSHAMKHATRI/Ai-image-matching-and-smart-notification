from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.auth.firebase import AuthenticatedUser, get_current_user
from app.database import db, repositories
from app.database.found_item_schemas import (
    AnalysisTriggerResponse,
    FoundItemCreate,
    FoundItemResponse,
)
from app.services.analysis_service import (
    AnalysisRequest,
    AnalysisUnavailable,
    get_analysis_provider,
)
from app.services.storage_service import store_image, validate_and_read_image

router = APIRouter(prefix="/api/found-items", tags=["found-items"])


def current_user_id(current_user: AuthenticatedUser) -> int:
    return db.ensure_user(current_user.uid)


def serialize_found_item(item: dict[str, object]) -> dict[str, object]:
    return {
        "id": item["id"],
        "status": item["status"],
        "found_date": item["found_at"],
        "found_location": item["location"],
        "campus": item["campus"],
        "image_reference": item["image_reference"],
        "analysis_status": item["analysis_status"],
        "analysis_error": item["analysis_error"],
        "created_at": item["created_at"],
        "updated_at": item["updated_at"],
    }


def found_item_or_404(user_id: int, item_id: int) -> dict[str, object]:
    item = repositories.get_found_item_for_user(user_id, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Found item not found.")
    return item


@router.post("", response_model=FoundItemResponse, status_code=status.HTTP_201_CREATED)
def create_found_item(
    found_item: FoundItemCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, object]:
    user_id = current_user_id(current_user)
    item_id = repositories.create_found_item(
        user_id,
        found_at=found_item.found_date.isoformat(),
        location=found_item.found_location,
        campus=found_item.campus,
    )
    return serialize_found_item(found_item_or_404(user_id, item_id))


@router.get("", response_model=list[FoundItemResponse])
def list_my_found_items(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> list[dict[str, object]]:
    user_id = current_user_id(current_user)
    return [serialize_found_item(item) for item in repositories.list_found_items_for_user(user_id)]


@router.get("/{item_id}", response_model=FoundItemResponse)
def get_my_found_item(
    item_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, object]:
    return serialize_found_item(found_item_or_404(current_user_id(current_user), item_id))


@router.post("/{item_id}/image", response_model=FoundItemResponse)
async def upload_found_item_image(
    item_id: int,
    image: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, object]:
    user_id = current_user_id(current_user)
    found_item = found_item_or_404(user_id, item_id)
    contents, content_type = await validate_and_read_image(image)
    try:
        stored_image = store_image(
            contents,
            content_type,
            current_user.uid,
            item_id,
            collection="found-items",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Image storage is temporarily unavailable.",
        ) from exc

    updated_item = repositories.update_found_item_for_user(
        user_id,
        item_id,
        {"image_reference": stored_image.path},
    )
    if updated_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Found item not found.")
    return serialize_found_item(updated_item)


@router.post("/{item_id}/analyze", response_model=AnalysisTriggerResponse)
def analyze_found_item(
    item_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, object]:
    user_id = current_user_id(current_user)
    found_item = found_item_or_404(user_id, item_id)
    image_reference = found_item["image_reference"]
    if not isinstance(image_reference, str) or not image_reference:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A found-item image is required before analysis.",
        )

    requested_at = datetime.now(timezone.utc).isoformat()
    repositories.update_found_item_for_user(
        user_id,
        item_id,
        {
            "analysis_status": "QUEUED",
            "analysis_error": None,
            "analysis_requested_at": requested_at,
        },
    )
    try:
        result = get_analysis_provider().analyze(AnalysisRequest(image_reference=image_reference))
    except AnalysisUnavailable:
        updated_item = repositories.update_found_item_for_user(
            user_id,
            item_id,
            {
                "analysis_status": "UNAVAILABLE",
                "analysis_error": "AI analysis is unavailable; reporting remains available.",
            },
        )
        return {
            "found_item": serialize_found_item(updated_item),  # type: ignore[arg-type]
            "accepted": False,
            "message": "Found item saved. AI analysis is not configured yet.",
        }

    updated_item = repositories.update_found_item_for_user(
        user_id,
        item_id,
        {
            "analysis_status": "FAILED",
            "analysis_error": "Analysis provider returned an unsupported Phase 6 response.",
            "analysis_completed_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    return {
        "found_item": serialize_found_item(updated_item),  # type: ignore[arg-type]
        "accepted": False,
        "message": "Found item saved, but analysis is not available in Phase 6.",
    }
