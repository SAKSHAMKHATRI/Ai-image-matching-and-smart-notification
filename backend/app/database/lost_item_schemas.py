import re
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LostItemBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_name: str = Field(min_length=2, max_length=120)
    category: str = Field(min_length=2, max_length=80)
    color: str | None = Field(default=None, max_length=60)
    brand: str | None = Field(default=None, max_length=80)
    lost_date: date
    approximate_location: str = Field(min_length=2, max_length=160)
    description: str = Field(min_length=10, max_length=2000)
    distinctive_features: str | None = Field(default=None, max_length=1000)
    image_reference: str | None = Field(default=None, max_length=500)

    @field_validator(
        "item_name",
        "category",
        "color",
        "brand",
        "approximate_location",
        "description",
        "distinctive_features",
        "image_reference",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        return stripped or None

    @field_validator("image_reference")
    @classmethod
    def validate_image_reference(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if "\x00" in value or not re.fullmatch(r"[A-Za-z0-9_./:-]+", value):
            raise ValueError("Image reference contains unsupported characters.")
        return value


class LostItemCreate(LostItemBase):
    pass


class LostItemUpdate(LostItemBase):
    pass


class LostItemResponse(LostItemBase):
    id: int
    status: str
    created_at: str
    updated_at: str
