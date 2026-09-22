from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.profile import router as profile_router
from app.api.lost_items import router as lost_items_router
from app.api.found_items import router as found_items_router
from app.api.matches import router as matches_router
from app.api.claims import router as claims_router
from app.api.admin import router as admin_router
from app.api.search import router as search_router
from app.auth.firebase import AuthenticatedUser, get_current_user
from app.config import get_cors_origins
from app.database.db import initialize_database

app = FastAPI(
    title="University AI Lost & Found API",
    version="0.1.0",
    description="Phase 1 authentication foundation.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
initialize_database()
app.include_router(profile_router)
app.include_router(lost_items_router)
app.include_router(found_items_router)
app.include_router(matches_router)
app.include_router(claims_router)
app.include_router(admin_router)
app.include_router(search_router)




@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/auth/me", response_model=AuthenticatedUser)
def get_authenticated_user(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    return current_user
