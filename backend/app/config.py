import json
import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class FirebaseConfigError(RuntimeError):
    """Raised when Firebase Admin configuration is missing or malformed."""


def get_cors_origins() -> list[str]:
    configured_origins = os.getenv(
        "BACKEND_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
    return [origin.strip() for origin in configured_origins.split(",") if origin.strip()]


@lru_cache

def get_firebase_options() -> dict[str, str]:
    service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if service_account_json:
        try:
            service_account = json.loads(service_account_json)
        except json.JSONDecodeError as exc:
            raise FirebaseConfigError(
                "FIREBASE_SERVICE_ACCOUNT_JSON must contain valid JSON."
            ) from exc
        required_fields = ("project_id", "client_email", "private_key")
        if any(not service_account.get(field) for field in required_fields):
            raise FirebaseConfigError(
                "FIREBASE_SERVICE_ACCOUNT_JSON is missing required fields."
            )
        return {
            "projectId": service_account["project_id"],
            "clientEmail": service_account["client_email"],
            "privateKey": service_account["private_key"],
        }

    project_id = os.getenv("FIREBASE_PROJECT_ID")
    client_email = os.getenv("FIREBASE_CLIENT_EMAIL")
    private_key = os.getenv("FIREBASE_PRIVATE_KEY")
    if not all((project_id, client_email, private_key)):
        raise FirebaseConfigError(
            "Firebase Admin configuration is incomplete. Set the service account "
            "JSON or FIREBASE_PROJECT_ID, FIREBASE_CLIENT_EMAIL, and "
            "FIREBASE_PRIVATE_KEY."
        )

    return {
        "projectId": project_id,
        "clientEmail": client_email,
        "privateKey": private_key.replace("\\n", "\n"),
    }
