import sqlite3

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth.firebase import AuthenticatedUser, get_current_user
from app.database import db
from app.database.schemas import (
    StudentProfileCreate,
    StudentProfileResponse,
    StudentProfileUpdate,
)

router = APIRouter(prefix="/api/profile", tags=["profile"])


def profile_or_404(firebase_uid: str) -> dict[str, object]:
    profile = db.get_profile(firebase_uid)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found.",
        )
    return profile


@router.get("", response_model=StudentProfileResponse)
def get_my_profile(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, object]:
    return profile_or_404(current_user.uid)


@router.post(
    "",
    response_model=StudentProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_my_profile(
    profile: StudentProfileCreate,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, object]:
    if db.get_profile(current_user.uid) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student profile already exists.",
        )

    try:
        return db.create_profile(current_user.uid, profile.model_dump())
    except sqlite3.IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Student profile already exists.",
        ) from exc


@router.patch("", response_model=StudentProfileResponse)
def update_my_profile(
    profile: StudentProfileUpdate,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, object]:
    updated_profile = db.update_profile(current_user.uid, profile.model_dump())
    if updated_profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found.",
        )
    return updated_profile
