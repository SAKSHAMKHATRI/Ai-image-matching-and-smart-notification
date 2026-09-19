import re
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StudentProfileBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    full_name: str = Field(min_length=2, max_length=100)
    roll_number: str = Field(min_length=1, max_length=50)
    class_section: str = Field(min_length=1, max_length=100)
    course_program: str = Field(min_length=1, max_length=150)
    semester: int = Field(ge=1, le=20)
    phone_number: str = Field(min_length=7, max_length=20)
    university_email: str = Field(min_length=3, max_length=254)
    campus: str = Field(min_length=1, max_length=100)

    @field_validator(
        "full_name",
        "roll_number",
        "class_section",
        "course_program",
        "phone_number",
        "university_email",
        "campus",
        mode="before",
    )
    @classmethod
    def strip_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return value.strip()

    @field_validator("university_email")
    @classmethod
    def validate_university_email(cls, value: str) -> str:
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("Enter a valid university email address.")
        return value.lower()

    @field_validator("phone_number")
    @classmethod
    def validate_phone_number(cls, value: str) -> str:
        if not re.fullmatch(r"\+?[0-9][0-9 ()-]{5,18}[0-9]", value):
            raise ValueError("Enter a valid phone number.")
        return value


class StudentProfileCreate(StudentProfileBase):
    pass


class StudentProfileUpdate(StudentProfileBase):
    pass


class StudentProfileResponse(StudentProfileBase):
    id: int
    firebase_uid: str
    created_at: str
    updated_at: str
