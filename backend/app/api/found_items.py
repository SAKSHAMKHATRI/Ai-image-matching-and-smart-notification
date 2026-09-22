import json
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.auth.firebase import AuthenticatedUser, get_current_user
from app.database import db, repositories
from app.database.found_item_schemas import (
    AnalysisTriggerResponse,
    FoundItemCreate,
    FoundItemResponse,
    FoundItemUpdate,
    ImageAnalysisPreviewResponse,
    OCRPreviewResponse,
)
from app.services.analysis_service import (
    AnalysisFailed,
    AnalysisRequest,
    AnalysisUnavailable,
    get_analysis_provider,
)
from app.services.embedding_service import get_embedding_provider, serialize_embedding
from app.services.matching_service import evaluate_and_persist_matches_for_found_item
from app.services.ocr_service import (
    OCRFailed,
    OCRRequest,
    OCRUnavailable,
    get_ocr_provider,
)
from app.services.storage_service import store_image, validate_and_read_image

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/found-items", tags=["found-items"])


def current_user_id(current_user: AuthenticatedUser) -> int:
    return db.ensure_user(current_user.uid)


def serialize_found_item(item: dict[str, Any]) -> dict[str, Any]:
    ai_attrs_raw = item.get("ai_attributes_json")
    ai_attributes: dict[str, Any] | None = None
    if isinstance(ai_attrs_raw, str) and ai_attrs_raw.strip():
        try:
            ai_attributes = json.loads(ai_attrs_raw)
        except Exception:
            ai_attributes = None

    return {
        "id": item["id"],
        "status": item["status"],
        "found_date": item["found_at"],
        "found_location": item.get("location"),
        "campus": item.get("campus"),
        "item_name": item.get("item_name"),
        "category": item.get("category"),
        "color": item.get("color"),
        "brand": item.get("brand"),
        "description": item.get("description"),
        "distinctive_features": item.get("distinctive_features"),
        "image_reference": item.get("image_reference"),
        "ai_attributes": ai_attributes,
        "analysis_status": item["analysis_status"],
        "analysis_error": item.get("analysis_error"),
        "created_at": item["created_at"],
        "updated_at": item["updated_at"],
    }


def found_item_or_404(user_id: int, item_id: int) -> dict[str, Any]:
    item = repositories.get_found_item_for_user(user_id, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Found item not found.")
    return item


@router.post("/analyze-image", response_model=ImageAnalysisPreviewResponse)
async def analyze_image_preview(
    image: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Analyze an uploaded image before creating the found item record."""
    contents, content_type = await validate_and_read_image(image)
    try:
        provider = get_analysis_provider()
        result = provider.analyze_bytes(contents, content_type=content_type)
        attrs = result.attributes
        features_list = attrs.get("visible_features", [])
        distinctive_features = ", ".join(features_list) if features_list else None
        visible_text_list = attrs.get("visible_text", [])
        if visible_text_list:
            text_str = ", ".join(str(t) for t in visible_text_list if str(t).strip())
            if text_str:
                if distinctive_features:
                    distinctive_features = f"{distinctive_features} (Text: {text_str})"
                else:
                    distinctive_features = f"Text: {text_str}"
        return {
            "success": True,
            "message": "AI analyzed the item photo successfully.",
            "description": result.description,
            "item_name": attrs.get("object_type"),
            "category": attrs.get("category"),
            "color": attrs.get("primary_color"),
            "brand": attrs.get("brand"),
            "distinctive_features": distinctive_features,
            "attributes": attrs,
        }
    except AnalysisUnavailable as exc:
        logger.info("Foundry analysis unavailable for preview: %s", exc)
        return {
            "success": False,
            "message": "AI analysis is unavailable; reporting remains available.",
            "description": None,
            "item_name": None,
            "category": None,
            "color": None,
            "brand": None,
            "distinctive_features": None,
            "attributes": None,
        }
    except Exception as exc:
        logger.warning("Foundry analysis preview failed: %s", exc)
        return {
            "success": False,
            "message": "AI analysis timed out or could not process image; you can enter details manually.",
            "description": None,
            "item_name": None,
            "category": None,
            "color": None,
            "brand": None,
            "distinctive_features": None,
            "attributes": None,
        }


@router.post("/extract-ocr", response_model=OCRPreviewResponse)
async def extract_ocr_preview(
    image: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """Extract visible text and writing (OCR) from an uploaded image."""
    contents, content_type = await validate_and_read_image(image)
    try:
        ocr_provider = get_ocr_provider()
        ocr_result = ocr_provider.extract_ocr_bytes(contents, content_type=content_type)
        return {
            "success": True,
            "message": (
                "Visible text extracted successfully."
                if ocr_result.detected_text_present
                else "No text detected in image."
            ),
            "detected_text_present": ocr_result.detected_text_present,
            "extracted_text": ocr_result.extracted_text,
            "sanitized_text": ocr_result.sanitized_text,
            "text_blocks": ocr_result.text_blocks,
            "confidence": ocr_result.confidence,
            "language": ocr_result.language,
            "has_sensitive_pii": ocr_result.has_sensitive_pii,
            "provider": ocr_result.provider,
            "status": ocr_result.status,
        }
    except OCRUnavailable as exc:
        logger.info("OCR service unavailable: %s", exc)
        return {
            "success": False,
            "message": "OCR service is not configured.",
            "detected_text_present": False,
            "extracted_text": "",
            "sanitized_text": "",
            "text_blocks": [],
            "confidence": None,
            "language": None,
            "has_sensitive_pii": False,
            "provider": "unavailable",
            "status": "UNAVAILABLE",
        }
    except Exception as exc:
        logger.warning("OCR preview extraction failed: %s", exc)
        return {
            "success": False,
            "message": "OCR extraction failed or timed out.",
            "detected_text_present": False,
            "extracted_text": "",
            "sanitized_text": "",
            "text_blocks": [],
            "confidence": None,
            "language": None,
            "has_sensitive_pii": False,
            "provider": "unknown",
            "status": "FAILED",
        }


@router.post("", response_model=FoundItemResponse, status_code=status.HTTP_201_CREATED)
def create_found_item(
    found_item: FoundItemCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    user_id = current_user_id(current_user)
    fields = {
        "found_at": found_item.found_date.isoformat(),
        "location": found_item.found_location,
        "campus": found_item.campus,
        "item_name": found_item.item_name,
        "category": found_item.category,
        "color": found_item.color,
        "brand": found_item.brand,
        "description": found_item.description,
        "distinctive_features": found_item.distinctive_features,
        "ai_attributes_json": found_item.ai_attributes_json,
    }
    non_null_fields = {k: v for k, v in fields.items() if v is not None}
    desc_text = found_item.description or found_item.item_name
    if desc_text and desc_text.strip():
        try:
            emb_provider = get_embedding_provider()
            emb_res = emb_provider.embed_text(desc_text)
            if emb_res.status == "SUCCESS":
                non_null_fields["image_embedding_blob"] = serialize_embedding(emb_res.vector)
        except Exception as exc:
            logger.warning("Failed to generate embedding on found item creation: %s", exc)

    item_id = repositories.create_found_item(user_id, **non_null_fields)
    created_item = found_item_or_404(user_id, item_id)
    try:
        evaluate_and_persist_matches_for_found_item(created_item)
    except Exception as exc:
        logger.warning("Automatic match evaluation for found item %d failed: %s", item_id, exc)
    return serialize_found_item(created_item)


@router.get("", response_model=list[FoundItemResponse])
def list_my_found_items(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> list[dict[str, Any]]:
    user_id = current_user_id(current_user)
    return [serialize_found_item(item) for item in repositories.list_found_items_for_user(user_id)]


@router.get("/{item_id}", response_model=FoundItemResponse)
def get_my_found_item(
    item_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    return serialize_found_item(found_item_or_404(current_user_id(current_user), item_id))


@router.patch("/{item_id}", response_model=FoundItemResponse)
def update_my_found_item(
    item_id: int,
    report: FoundItemUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    user_id = current_user_id(current_user)
    found_item_or_404(user_id, item_id)
    fields = {
        "found_at": report.found_date.isoformat() if report.found_date else None,
        "location": report.found_location,
        "campus": report.campus,
        "item_name": report.item_name,
        "category": report.category,
        "color": report.color,
        "brand": report.brand,
        "description": report.description,
        "distinctive_features": report.distinctive_features,
        "ai_attributes_json": report.ai_attributes_json,
    }
    non_null_fields = {k: v for k, v in fields.items() if v is not None}

    # If description or item_name was updated, regenerate embedding blob
    desc_text = report.description or report.item_name
    if desc_text and desc_text.strip():
        try:
            emb_provider = get_embedding_provider()
            emb_res = emb_provider.embed_text(desc_text)
            if emb_res.status == "SUCCESS":
                non_null_fields["image_embedding_blob"] = serialize_embedding(emb_res.vector)
        except Exception as exc:
            logger.warning("Failed to regenerate embedding on found item update: %s", exc)

    updated_item = repositories.update_found_item_for_user(user_id, item_id, non_null_fields)
    if updated_item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Found item not found.")
    try:
        evaluate_and_persist_matches_for_found_item(updated_item)
    except Exception as exc:
        logger.warning("Automatic match evaluation for updated found item %d failed: %s", item_id, exc)
    return serialize_found_item(updated_item)


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_found_item(
    item_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> None:
    user_id = current_user_id(current_user)
    if not repositories.delete_found_item_for_user(user_id, item_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Found item not found.")


@router.post("/{item_id}/image", response_model=FoundItemResponse)
async def upload_found_item_image(
    item_id: int,
    image: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    user_id = current_user_id(current_user)
    found_item_or_404(user_id, item_id)
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
) -> dict[str, Any]:
    user_id = current_user_id(current_user)
    found_item = found_item_or_404(user_id, item_id)
    image_reference = found_item.get("image_reference")
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
        provider = get_analysis_provider()
        result = provider.analyze(AnalysisRequest(image_reference=image_reference))
        attrs = result.attributes
        completed_at = datetime.now(timezone.utc).isoformat()

        update_data: dict[str, Any] = {
            "analysis_status": "ANALYZED",
            "status": "ANALYZED",
            "analysis_error": None,
            "analysis_completed_at": completed_at,
            "ai_attributes_json": json.dumps(attrs),
        }
        # Populate empty item fields with extracted attributes
        if not found_item.get("description") and result.description:
            update_data["description"] = result.description
        if not found_item.get("item_name") and attrs.get("object_type"):
            update_data["item_name"] = str(attrs["object_type"])
        if not found_item.get("category") and attrs.get("category"):
            update_data["category"] = str(attrs["category"])
        if not found_item.get("color") and attrs.get("primary_color"):
            update_data["color"] = str(attrs["primary_color"])
        if not found_item.get("brand") and attrs.get("brand"):
            update_data["brand"] = str(attrs["brand"])
        if not found_item.get("distinctive_features") and attrs.get("visible_features"):
            features_list = attrs["visible_features"]
            if isinstance(features_list, list) and features_list:
                update_data["distinctive_features"] = ", ".join(str(f) for f in features_list)

        # Generate image embedding blob from analyzed visual description
        try:
            emb_provider = get_embedding_provider()
            desc_text = result.description or str(attrs.get("object_type", "Found item"))
            emb_res = emb_provider.embed_text(desc_text)
            if emb_res.status == "SUCCESS":
                update_data["image_embedding_blob"] = serialize_embedding(emb_res.vector)
        except Exception as exc:
            logger.warning("Failed to generate image embedding for found item: %s", exc)

        updated_item = repositories.update_found_item_for_user(user_id, item_id, update_data)
        if updated_item:
            try:
                evaluate_and_persist_matches_for_found_item(updated_item)
            except Exception as exc:
                logger.warning("Automatic match evaluation for analyzed found item %d failed: %s", item_id, exc)
        return {
            "found_item": serialize_found_item(updated_item),  # type: ignore[arg-type]
            "accepted": True,
            "message": "Found item analyzed successfully.",
            "attributes": attrs,
        }
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
            "attributes": None,
        }
    except (AnalysisFailed, Exception) as exc:
        logger.warning("Found item analysis failed: %s", exc)
        updated_item = repositories.update_found_item_for_user(
            user_id,
            item_id,
            {
                "analysis_status": "FAILED",
                "analysis_error": "AI analysis timed out or could not complete.",
                "analysis_completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return {
            "found_item": serialize_found_item(updated_item),  # type: ignore[arg-type]
            "accepted": False,
            "message": "Found item saved, but AI analysis could not be completed.",
            "attributes": None,
        }
