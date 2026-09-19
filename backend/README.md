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

Set the Firebase Admin environment variables from the repository `.env.example` before using protected routes. The backend verifies Firebase ID tokens server-side and does not trust client-provided identity fields.

Run backend tests with:

```powershell
python -m pytest
```

Lost-item endpoints are available under `/api/lost-items` and found-item endpoints under `/api/found-items`; both are scoped to the verified Firebase user. Configure `FIREBASE_STORAGE_BUCKET` and Firebase Admin credentials locally before using image uploads. Phase 6 exposes an analysis trigger, but the provider remains intentionally unavailable until Phase 7.
