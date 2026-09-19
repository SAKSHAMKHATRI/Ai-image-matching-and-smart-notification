from functools import lru_cache
from typing import Any

import firebase_admin
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from firebase_admin import auth, credentials, storage
from pydantic import BaseModel, ConfigDict

from app.config import FirebaseConfigError, get_firebase_options


class AuthenticatedUser(BaseModel):
    model_config = ConfigDict(extra="forbid")

    uid: str
    email: str | None = None
    email_verified: bool = False


bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache

def get_firebase_app() -> firebase_admin.App:
    try:
        options = get_firebase_options()
        service_account = credentials.Certificate(
            {
                "type": "service_account",
                "project_id": options["projectId"],
                "client_email": options["clientEmail"],
                "private_key": options["privateKey"],
            }
        )
        return firebase_admin.initialize_app(service_account)
    except FirebaseConfigError:
        raise
    except Exception as exc:
        raise FirebaseConfigError("Firebase Admin initialization failed.") from exc


@lru_cache
def get_storage_bucket():
    from app.config import get_storage_bucket_name

    try:
        return storage.bucket(get_storage_bucket_name(), app=get_firebase_app())
    except FirebaseConfigError:
        raise
    except Exception as exc:
        raise FirebaseConfigError("Firebase Storage initialization failed.") from exc


def verify_firebase_token(token: str) -> dict[str, Any]:
    try:
        return auth.verify_id_token(token, app=get_firebase_app())
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_current_user(
    credentials_header: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> AuthenticatedUser:
    if credentials_header is None or credentials_header.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        decoded_token = verify_firebase_token(credentials_header.credentials)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    uid = decoded_token.get("uid")
    if not isinstance(uid, str) or not uid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    email = decoded_token.get("email")
    return AuthenticatedUser(
        uid=uid,
        email=email if isinstance(email, str) else None,
        email_verified=decoded_token.get("email_verified") is True,
    )
