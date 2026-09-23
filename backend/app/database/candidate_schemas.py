from typing import Any

from pydantic import BaseModel, Field


class CandidateSearchRequest(BaseModel):
    """Request body for POST /api/matches/search."""

    found_item_id: int
    category: str | None = None
    campus: str | None = None
    location: str | None = None
    brand: str | None = None
    date_window_days: int = Field(default=90, ge=1, le=365)
    max_results: int = Field(default=50, ge=1, le=200)


class CandidateItemResponse(BaseModel):
    """Safe subset of a lost item returned as a candidate match."""

    id: int
    status: str
    item_name: str
    category: str | None = None
    color: str | None = None
    brand: str | None = None
    campus: str | None = None
    lost_date: str | None = None
    approximate_location: str | None = None
    description: str | None = None
    distinctive_features: str | None = None
    image_reference: str | None = None
    created_at: str


class CandidateSearchResponse(BaseModel):
    """Response for POST /api/matches/search."""

    found_item_id: int
    candidates: list[CandidateItemResponse]
    total_candidates: int
    filters_applied: dict


class ScoredMatchItemResponse(BaseModel):
    """Safe, scored match representation for UI display."""

    id: int
    lost_item_id: int | None = None
    found_item_id: int | None = None
    match_id: int | None = None
    status: str
    item_name: str
    category: str | None = None
    color: str | None = None
    brand: str | None = None
    campus: str | None = None
    lost_date: str | None = None
    found_date: str | None = None
    approximate_location: str | None = None
    found_location: str | None = None
    description: str | None = None
    distinctive_features: str | None = None
    image_reference: str | None = None
    finder_name: str | None = None
    found_by: str | None = None
    lost_item_name: str | None = None
    score: float
    score_percent: int
    classification: str
    classification_label: str
    reasons: list[str] = []
    components: dict[str, Any] = {}
    created_at: str


class MatchSearchResponse(BaseModel):
    """Full evaluated match response for a found item or lost item."""

    found_item_id: int | None = None
    lost_item_id: int | None = None
    matches: list[ScoredMatchItemResponse]
    total_matches: int
    strong_matches_count: int
    possible_matches_count: int
    low_confidence_count: int
    disclaimer: str
    message: str | None = None

