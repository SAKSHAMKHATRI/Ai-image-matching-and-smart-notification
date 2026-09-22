from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FoundItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found_date: date
    found_location: str | None = Field(default=None, max_length=160)
    campus: str | None = Field(default=None, max_length=100)
    item_name: str | None = Field(default=None, max_length=120)
    category: str | None = Field(default=None, max_length=80)
    color: str | None = Field(default=None, max_length=60)
    brand: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=2000)
    distinctive_features: str | None = Field(default=None, max_length=1000)
    ai_attributes_json: str | None = None

    @field_validator(
        "found_location",
        "campus",
        "item_name",
        "category",
        "color",
        "brand",
        "description",
        "distinctive_features",
        mode="before",
    )
    @classmethod
    def strip_optional_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        return stripped or None


class FoundItemUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found_date: date | None = None
    found_location: str | None = Field(default=None, max_length=160)
    campus: str | None = Field(default=None, max_length=100)
    item_name: str | None = Field(default=None, max_length=120)
    category: str | None = Field(default=None, max_length=80)
    color: str | None = Field(default=None, max_length=60)
    brand: str | None = Field(default=None, max_length=80)
    description: str | None = Field(default=None, max_length=2000)
    distinctive_features: str | None = Field(default=None, max_length=1000)
    ai_attributes_json: str | None = None

    @field_validator(
        "found_location",
        "campus",
        "item_name",
        "category",
        "color",
        "brand",
        "description",
        "distinctive_features",
        mode="before",
    )
    @classmethod
    def strip_optional_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        return stripped or None


class FoundItemResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    status: str
    found_date: date
    found_location: str | None = None
    campus: str | None = None
    item_name: str | None = None
    category: str | None = None
    color: str | None = None
    brand: str | None = None
    description: str | None = None
    distinctive_features: str | None = None
    image_reference: str | None = None
    ai_attributes: dict[str, Any] | None = None
    analysis_status: str
    analysis_error: str | None = None
    created_at: str
    updated_at: str


class AnalysisTriggerResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found_item: FoundItemResponse
    accepted: bool
    message: str
    attributes: dict[str, Any] | None = None


class ImageAnalysisPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    message: str
    description: str | None = None
    item_name: str | None = None
    category: str | None = None
    color: str | None = None
    brand: str | None = None
    distinctive_features: str | None = None
    attributes: dict[str, Any] | None = None


class OCRPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    success: bool
    message: str
    detected_text_present: bool = False
    extracted_text: str = ""
    sanitized_text: str = ""
    text_blocks: list[str] = Field(default_factory=list)
    confidence: float | None = None
    language: str | None = None
    has_sensitive_pii: bool = False
    provider: str = "unknown"
    status: str = "SUCCESS"
