import logging
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query

from app.auth.firebase import AuthenticatedUser, get_current_user
from app.database import repositories
from app.database.search_schemas import (
    ManualSearchResult,
    PublicFoundItemResponse,
    PublicLostItemResponse,
    SearchSystemStatusResponse,
)
from app.services.embedding_service import get_embedding_provider
from app.services.foundry_client import FoundryConfigurationError, get_foundry_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])


@router.get("/status", response_model=SearchSystemStatusResponse)
def get_search_system_status(
    _current_user: AuthenticatedUser = Depends(get_current_user),
) -> SearchSystemStatusResponse:
    """Return system AI health and fallback status."""
    foundry_ok = False
    try:
        get_foundry_config()
        foundry_ok = True
    except (FoundryConfigurationError, Exception):
        foundry_ok = False

    embeddings_ok = False
    try:
        provider = get_embedding_provider()
        embeddings_ok = provider is not None
    except Exception:
        embeddings_ok = False

    ocr_ok = foundry_ok  # OCR relies on Foundry client

    ai_available = foundry_ok and embeddings_ok

    return SearchSystemStatusResponse(
        ai_available=ai_available,
        foundry_configured=foundry_ok,
        ocr_configured=ocr_ok,
        embeddings_configured=embeddings_ok,
        manual_search_available=True,
    )


@router.get("/found-items", response_model=ManualSearchResult[PublicFoundItemResponse])
def search_found_items(
    query: str | None = Query(default=None, description="Free text keyword search"),
    category: str | None = Query(default=None, description="Item category filter"),
    campus: str | None = Query(default=None, description="Campus filter"),
    location: str | None = Query(default=None, description="Location text filter"),
    color: str | None = Query(default=None, description="Primary color filter"),
    brand: str | None = Query(default=None, description="Brand filter"),
    from_date: date | None = Query(default=None, description="Earliest found date"),
    to_date: date | None = Query(default=None, description="Latest found date"),
    limit: int = Query(default=50, ge=1, le=100, description="Page limit"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
    _current_user: AuthenticatedUser = Depends(get_current_user),
) -> ManualSearchResult[PublicFoundItemResponse]:
    """Search active/analyzed found items with optional keyword and metadata filters."""
    items_raw, total = repositories.search_public_found_items(
        query=query,
        category=category,
        campus=campus,
        location=location,
        color=color,
        brand=brand,
        date_from=str(from_date) if from_date else None,
        date_to=str(to_date) if to_date else None,
        limit=limit,
        offset=offset,
    )

    items = []
    for item in items_raw:
        finder_id = item.get("user_id")
        finder_display = "Campus Student"
        if finder_id:
            try:
                from app.services.notification_service import get_user_display_name

                finder_display = get_user_display_name(finder_id)
            except Exception:
                finder_display = "Campus Student"

        items.append(
            PublicFoundItemResponse(
                id=item["id"],
                status=item["status"],
                found_date=item.get("found_at") or "",
                found_location=item.get("location"),
                campus=item.get("campus"),
                item_name=item.get("item_name"),
                category=item.get("category"),
                color=item.get("color"),
                brand=item.get("brand"),
                description=item.get("description"),
                distinctive_features=item.get("distinctive_features"),
                image_reference=item.get("image_reference"),
                found_by=finder_display,
                finder_name=finder_display,
                created_at=item.get("created_at") or "",
            )
        )

    filters_applied: dict[str, Any] = {}
    if query:
        filters_applied["query"] = query
    if category:
        filters_applied["category"] = category
    if campus:
        filters_applied["campus"] = campus
    if location:
        filters_applied["location"] = location
    if color:
        filters_applied["color"] = color
    if brand:
        filters_applied["brand"] = brand
    if from_date:
        filters_applied["from_date"] = str(from_date)
    if to_date:
        filters_applied["to_date"] = str(to_date)

    return ManualSearchResult[PublicFoundItemResponse](
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        filters_applied=filters_applied,
    )


@router.get("/lost-items", response_model=ManualSearchResult[PublicLostItemResponse])
def search_lost_items(
    query: str | None = Query(default=None, description="Free text keyword search"),
    category: str | None = Query(default=None, description="Item category filter"),
    campus: str | None = Query(default=None, description="Campus filter"),
    location: str | None = Query(default=None, description="Location text filter"),
    color: str | None = Query(default=None, description="Primary color filter"),
    brand: str | None = Query(default=None, description="Brand filter"),
    from_date: date | None = Query(default=None, description="Earliest lost date"),
    to_date: date | None = Query(default=None, description="Latest lost date"),
    limit: int = Query(default=50, ge=1, le=100, description="Page limit"),
    offset: int = Query(default=0, ge=0, description="Page offset"),
    _current_user: AuthenticatedUser = Depends(get_current_user),
) -> ManualSearchResult[PublicLostItemResponse]:
    """Search active lost items with optional keyword and metadata filters."""
    items_raw, total = repositories.search_public_lost_items(
        query=query,
        category=category,
        campus=campus,
        location=location,
        color=color,
        brand=brand,
        date_from=str(from_date) if from_date else None,
        date_to=str(to_date) if to_date else None,
        limit=limit,
        offset=offset,
    )

    items = [
        PublicLostItemResponse(
            id=item["id"],
            status=item["status"],
            lost_date=item.get("lost_at") or "",
            approximate_location=item.get("location"),
            campus=item.get("campus"),
            item_name=item.get("item_name") or "Unknown Item",
            category=item.get("category"),
            color=item.get("color"),
            brand=item.get("brand"),
            description=item.get("description"),
            distinctive_features=item.get("distinctive_features"),
            image_reference=item.get("image_reference"),
            created_at=item.get("created_at") or "",
        )
        for item in items_raw
    ]

    filters_applied: dict[str, Any] = {}
    if query:
        filters_applied["query"] = query
    if category:
        filters_applied["category"] = category
    if campus:
        filters_applied["campus"] = campus
    if location:
        filters_applied["location"] = location
    if color:
        filters_applied["color"] = color
    if brand:
        filters_applied["brand"] = brand
    if from_date:
        filters_applied["from_date"] = str(from_date)
    if to_date:
        filters_applied["to_date"] = str(to_date)

    return ManualSearchResult[PublicLostItemResponse](
        items=items,
        total=total,
        limit=limit,
        offset=offset,
        filters_applied=filters_applied,
    )
