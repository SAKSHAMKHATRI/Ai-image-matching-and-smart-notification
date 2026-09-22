# Backend

FastAPI service for the University AI Lost & Found platform. Phase 4 adds authenticated lost-item reporting and management on the Phase 3 SQLite foundation.

## Local setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

The public health check is available at `http://127.0.0.1:8000/health`.

## Firebase Admin configuration

Preferred setup: generate a Firebase Admin service-account JSON locally (Firebase Console → Project settings → Service accounts) and point `FIREBASE_SERVICE_ACCOUNT_PATH` in the local `backend/.env` at it. The file is gitignored and its contents are never logged. Alternatives: `FIREBASE_SERVICE_ACCOUNT_JSON` (inline JSON) or the individual `FIREBASE_PROJECT_ID` / `FIREBASE_CLIENT_EMAIL` / `FIREBASE_PRIVATE_KEY` variables — all documented in the repository `.env.example`.

The backend verifies Firebase ID tokens server-side and does not trust client-provided identity fields.

Run backend tests with:

```powershell
python -m pytest
```

Lost-item endpoints are available under `/api/lost-items` and found-item endpoints under `/api/found-items`; both are scoped to the verified Firebase user. Configure `FIREBASE_STORAGE_BUCKET` and Firebase Admin credentials locally before using image uploads. Phase 7 adds the backend-only Foundry client; keep its project endpoint, API key, and model name in the local backend `.env`.
