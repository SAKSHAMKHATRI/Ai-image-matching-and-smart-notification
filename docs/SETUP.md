# Phase 0 Setup

Phase 0 provides a minimal React/Vite/TypeScript frontend and FastAPI backend. Later features are intentionally not included.

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite, normally `http://localhost:5173`.

The authentication UI requires the `VITE_FIREBASE_*` web configuration values in `.env`. Placeholder values intentionally show a configuration error instead of connecting to Firebase.

## Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

The health endpoint is `http://127.0.0.1:8000/health`.

The protected identity endpoint is `http://127.0.0.1:8000/api/auth/me` and requires a Firebase ID token in the `Authorization: Bearer` header.

Authenticated lost-item reporting uses `/api/lost-items`. Phase 5 uploads JPEG, PNG, and WebP files up to 5 MB through the backend to Firebase Storage; SQLite stores only the generated storage path.

Deploy `storage.rules` to Firebase Storage so browser clients cannot access the bucket directly. The backend Firebase Admin SDK bypasses client rules and remains the only storage access path.

For local browser requests, `BACKEND_CORS_ORIGINS` allows the two default Vite origins. Set it explicitly when using another frontend origin.

## Environment and secrets

Copy `.env.example` to `.env` for local configuration. `.env` is ignored by Git. Do not store credentials, service account files, or private API keys in the repository.
