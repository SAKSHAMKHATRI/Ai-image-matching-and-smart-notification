from datetime import date
from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ManualSearchParams(BaseModel):
    query: str | None = None
    category: str | None = None
    campus: str | None = None
    location: str | None = None
    color: str | None = None
    brand: str | None = None
    from_date: date | None = None
    to_date: date | None = None
    limit: int = Field(default=50, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class PublicFoundItemResponse(BaseModel):
    id: int
    status: str
    found_date: str
    found_location: str | None = None
    campus: str | None = None
    item_name: str | None = None
    category: str | None = None
    color: str | None = None
    brand: str | None = None
    description: str | None = None
    distinctive_features: str | None = None
    image_reference: str | None = None
    found_by: str | None = None
    finder_name: str | None = None
    created_at: str


class PublicLostItemResponse(BaseModel):
    id: int
    status: str
    lost_date: str
    approximate_location: str | None = None
    campus: str | None = None
    item_name: str
    category: str | None = None
    color: str | None = None
    brand: str | None = None
    description: str | None = None
    distinctive_features: str | None = None
    image_reference: str | None = None
    created_at: str


class ManualSearchResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
    filters_applied: dict[str, Any]


class SearchSystemStatusResponse(BaseModel):
    ai_available: bool
    foundry_configured: bool
    ocr_configured: bool
    embeddings_configured: bool
    manual_search_available: bool = True
