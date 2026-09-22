import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.database import repositories

logger = logging.getLogger(__name__)

DEFAULT_DATE_WINDOW_DAYS = 90
DEFAULT_MAX_RESULTS = 50
MAX_RESULTS_CAP = 200


@dataclass
class CandidateFilter:
    """Metadata filters for candidate retrieval."""

    category: str | None = None
    campus: str | None = None
    location: str | None = None
    brand: str | None = None
    date_window_days: int = DEFAULT_DATE_WINDOW_DAYS
    max_results: int = DEFAULT_MAX_RESULTS


def auto_filter_from_found_item(found_item: dict[str, Any]) -> CandidateFilter:
    """Derive a CandidateFilter from a found item's own metadata.

    Uses the found item's category, campus, and brand when available so the
    caller doesn't need to duplicate those values in the request body.
    """
    return CandidateFilter(
        category=found_item.get("category") or None,
        campus=found_item.get("campus") or None,
        brand=found_item.get("brand") or None,
    )


def _safe_candidate(row: dict[str, Any]) -> dict[str, Any]:
    """Convert a raw lost-item row into a privacy-safe candidate dict."""
    return {
        "id": row["id"],
        "status": row["status"],
        "item_name": row["item_name"],
        "category": row.get("category"),
        "color": row.get("color"),
        "brand": row.get("brand"),
        "campus": row.get("campus"),
        "lost_date": row.get("lost_at"),
        "approximate_location": row.get("location"),
        "description": row.get("description"),
        "distinctive_features": row.get("distinctive_features"),
        "image_reference": row.get("image_reference"),
        "created_at": row["created_at"],
    }


def retrieve_candidates(
    found_item_id: int,
    filters: CandidateFilter,
) -> dict[str, Any]:
    """Retrieve active lost-item candidates matching metadata filters.

    Returns a dict containing the found_item_id, list of safe candidate dicts,
    total count, and the filters that were actually applied.
    """
    found_item = repositories.get_found_item(found_item_id)
    if found_item is None:
        raise ValueError(f"Found item {found_item_id} does not exist.")

    # Merge explicit filters with auto-derived values from the found item
    effective_category = filters.category
    effective_campus = filters.campus
    effective_brand = filters.brand

    # If no explicit filter provided, use the found item's own metadata
    if effective_category is None:
        effective_category = found_item.get("category") or None
    if effective_campus is None:
        effective_campus = found_item.get("campus") or None
    if effective_brand is None:
        effective_brand = found_item.get("brand") or None

    # Calculate date window:
    # Use max(today, found_date) as reference date to handle future/suspicious found dates or timezone offsets
    date_window_days = max(1, min(filters.date_window_days, 365))
    today_dt = datetime.now(timezone.utc).date()
    found_dt = None
    found_at_str = found_item.get("found_at")
    if found_at_str:
        try:
            val = str(found_at_str).strip()
            found_dt = datetime.strptime(
                val.split("T")[0] if "T" in val else val, "%Y-%m-%d"
            ).date()
        except Exception:
            found_dt = None

    ref_date = max(today_dt, found_dt) if found_dt else today_dt
    date_from = (ref_date - timedelta(days=date_window_days)).strftime("%Y-%m-%d")
    date_to = (ref_date + timedelta(days=7)).strftime("%Y-%m-%d")

    max_results = max(1, min(filters.max_results, MAX_RESULTS_CAP))

    # Build the filters dict for logging
    filters_applied: dict[str, Any] = {"status": "ACTIVE"}
    if effective_category:
        filters_applied["category"] = effective_category
    if effective_campus:
        filters_applied["campus"] = effective_campus
    if filters.location:
        filters_applied["location"] = filters.location
    if effective_brand:
        filters_applied["brand"] = effective_brand
    filters_applied["date_from"] = date_from
    filters_applied["date_to"] = date_to
    filters_applied["max_results"] = max_results

    logger.info(
        "Retrieving candidates for found_item_id=%d with filters=%s",
        found_item_id,
        filters_applied,
    )

    rows = repositories.query_active_lost_items(
        category=effective_category,
        campus=effective_campus,
        location_like=filters.location,
        brand=effective_brand,
        date_from=date_from,
        date_to=date_to,
        limit=max_results,
    )

    candidates = [_safe_candidate(row) for row in rows]

    return {
        "found_item_id": found_item_id,
        "candidates": candidates,
        "total_candidates": len(candidates),
        "filters_applied": filters_applied,
    }
