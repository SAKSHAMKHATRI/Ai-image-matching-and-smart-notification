import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.auth.firebase import AuthenticatedUser, get_current_user
from app.database import db, repositories
from app.database.candidate_schemas import (
    CandidateSearchRequest,
    CandidateSearchResponse,
    MatchSearchResponse,
)
from app.services.candidate_service import CandidateFilter, retrieve_candidates
from app.services.matching_service import (
    evaluate_and_persist_matches_for_found_item,
    get_lost_item_matches_response,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/matches", tags=["matches"])


def _evaluate_and_save_matches(
    found_item: dict[str, Any],
    filters: CandidateFilter | None = None,
) -> dict[str, Any]:
    return evaluate_and_persist_matches_for_found_item(found_item, filters)


@router.post("/search", response_model=CandidateSearchResponse)
def search_candidates(
    request: CandidateSearchRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Search for active lost-item candidates matching a found item's metadata.

    The authenticated user must own the found item referenced by found_item_id.
    Returns a filtered list of candidate lost items (metadata only, no scoring).
    """
    user_id = db.ensure_user(current_user.uid)

    found_item = repositories.get_found_item_for_user(user_id, request.found_item_id)
    if found_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Found item not found or not owned by this user.",
        )

    filters = CandidateFilter(
        category=request.category,
        campus=request.campus,
        location=request.location,
        brand=request.brand,
        date_window_days=request.date_window_days,
        max_results=request.max_results,
    )

    try:
        result = retrieve_candidates(request.found_item_id, filters)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Candidate retrieval failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Candidate retrieval failed.",
        ) from exc

    return result


@router.post("/evaluate", response_model=MatchSearchResponse)
def evaluate_matches(
    request: CandidateSearchRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Retrieve and score candidate lost items for a found item with full explanations.

    Guards private owner data and includes deterministic component explanations.
    """
    user_id = db.ensure_user(current_user.uid)

    found_item = repositories.get_found_item_for_user(user_id, request.found_item_id)
    if found_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Found item not found or not owned by this user.",
        )

    filters = CandidateFilter(
        category=request.category,
        campus=request.campus,
        location=request.location,
        brand=request.brand,
        date_window_days=request.date_window_days,
        max_results=request.max_results,
    )

    try:
        return _evaluate_and_save_matches(found_item, filters)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        logger.exception("Match evaluation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Match evaluation failed.",
        ) from exc


@router.get("/found/{found_item_id}", response_model=MatchSearchResponse)
def get_found_item_matches(
    found_item_id: int,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Get evaluated match results for a given found item."""
    user_id = db.ensure_user(current_user.uid)

    found_item = repositories.get_found_item_for_user(user_id, found_item_id)
    if found_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Found item not found or not owned by this user.",
        )

    filters = CandidateFilter()
    return _evaluate_and_save_matches(found_item, filters)


@router.get("/lost/{lost_item_id}", response_model=MatchSearchResponse)
def get_lost_item_matches(
    lost_item_id: int,
    refresh: bool = Query(default=False),
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Get evaluated match results for a given lost item."""
    user_id = db.ensure_user(current_user.uid)

    lost_item = repositories.get_lost_item_for_user(user_id, lost_item_id)
    if lost_item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lost item not found or not owned by this user.",
        )

    return get_lost_item_matches_response(lost_item, refresh=refresh)
