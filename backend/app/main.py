from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.auth.firebase import AuthenticatedUser, get_current_user
from app.config import get_cors_origins

app = FastAPI(
    title="University AI Lost & Found API",
    version="0.1.0",
    description="Phase 1 authentication foundation.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/auth/me", response_model=AuthenticatedUser)
def get_authenticated_user(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    return current_user
