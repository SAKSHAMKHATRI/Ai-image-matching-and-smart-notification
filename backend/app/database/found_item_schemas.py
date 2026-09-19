from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FoundItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    found_date: date
    found_location: str | None = Field(default=None, max_length=160)
    campus: str | None = Field(default=None, max_length=100)

    @field_validator("found_location", "campus", mode="before")
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
    found_location: str | None
    campus: str | None
    image_reference: str | None
    analysis_status: str
    analysis_error: str | None
    created_at: str
    updated_at: str


class AnalysisTriggerResponse(BaseModel):
    found_item: FoundItemResponse
    accepted: bool
    message: str
