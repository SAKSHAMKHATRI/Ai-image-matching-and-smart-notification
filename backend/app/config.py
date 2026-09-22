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


_SERVICE_ACCOUNT_REQUIRED_FIELDS = (
    "project_id",
    "client_email",
    "private_key",
    "token_uri",
)


def _service_account_options(service_account: object) -> dict[str, str]:
    """Validate a parsed service-account dict and return Firebase options."""

    if not isinstance(service_account, dict):
        raise FirebaseConfigError(
            "Firebase service account must be a JSON object."
        )
    if any(not service_account.get(field) for field in _SERVICE_ACCOUNT_REQUIRED_FIELDS):
        raise FirebaseConfigError(
            "Firebase service account is missing required fields."
        )
    private_key = service_account["private_key"]
    if not isinstance(private_key, str):
        raise FirebaseConfigError(
            "Firebase service account private key is malformed."
        )
    return {
        "projectId": service_account["project_id"],
        "clientEmail": service_account["client_email"],
        "privateKey": private_key.replace("\\n", "\n"),
        "tokenUri": service_account["token_uri"],
    }


def _load_service_account_file(path: str) -> dict[str, str]:
    """Load a Firebase Admin service-account JSON file from disk.

    The file path is never logged and its contents are never printed.
    """
    candidate = os.path.expanduser(path)
    if not os.path.exists(candidate) and not os.path.isabs(path):
        alt_path = os.path.join("backend", path)
        if os.path.exists(alt_path):
            candidate = alt_path

    try:
        with open(candidate, encoding="utf-8") as handle:
            service_account = json.load(handle)
    except FileNotFoundError as exc:
        raise FirebaseConfigError(
            "FIREBASE_SERVICE_ACCOUNT_PATH points to a missing file."
        ) from exc
    except OSError as exc:
        raise FirebaseConfigError(
            "FIREBASE_SERVICE_ACCOUNT_PATH points to an unreadable file."
        ) from exc
    except json.JSONDecodeError as exc:
        raise FirebaseConfigError(
            "FIREBASE_SERVICE_ACCOUNT_PATH must contain valid JSON."
        ) from exc
    return _service_account_options(service_account)


@lru_cache
def get_firebase_options() -> dict[str, str]:
    # Preferred: path to a local service-account JSON file (gitignored).
    service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
    if service_account_path:
        return _load_service_account_file(service_account_path)

    service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")
    if service_account_json:
        try:
            service_account = json.loads(service_account_json)
        except json.JSONDecodeError as exc:
            raise FirebaseConfigError(
                "FIREBASE_SERVICE_ACCOUNT_JSON must contain valid JSON."
            ) from exc
        return _service_account_options(service_account)

    project_id = os.getenv("FIREBASE_PROJECT_ID")
    client_email = os.getenv("FIREBASE_CLIENT_EMAIL")
    private_key = os.getenv("FIREBASE_PRIVATE_KEY")
    if not all((project_id, client_email, private_key)):
        raise FirebaseConfigError(
            "Firebase Admin configuration is incomplete. Set "
            "FIREBASE_SERVICE_ACCOUNT_PATH, FIREBASE_SERVICE_ACCOUNT_JSON, or "
            "FIREBASE_PROJECT_ID, FIREBASE_CLIENT_EMAIL, and FIREBASE_PRIVATE_KEY."
        )

    return {
        "projectId": project_id,
        "clientEmail": client_email,
        "privateKey": private_key.replace("\\n", "\n"),
        "tokenUri": "https://oauth2.googleapis.com/token",
    }


def get_storage_bucket_name() -> str:
    bucket_name = os.getenv("FIREBASE_STORAGE_BUCKET")
    if bucket_name and not bucket_name.startswith("replace-with-"):
        return bucket_name.strip()

    try:
        options = get_firebase_options()
        project_id = options.get("projectId")
        if project_id and isinstance(project_id, str) and project_id.strip():
            return f"{project_id.strip()}.appspot.com"
    except Exception:
        pass

    raise FirebaseConfigError("Firebase Storage bucket is not configured.")
