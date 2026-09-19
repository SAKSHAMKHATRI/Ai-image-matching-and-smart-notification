# University AI Lost & Found

Phase 3 establishes the repository foundation, Firebase authentication, private student profiles, and the SQLite data model foundation for the university-only Lost & Found platform.

## Repository layout

- `frontend/`: React + Vite + TypeScript application
- `backend/`: Python FastAPI service
- `docs/`: setup and architecture boundary documentation
- `doc/`: master project context and GitHub issue backlog

## Prerequisites

- Node.js 20 or newer
- npm 10 or newer
- Python 3.11 or newer

## Start the frontend

```powershell
cd frontend
npm install
npm run dev
```

Open the URL printed by Vite, normally `http://localhost:5173`.

## Start the backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

The health endpoint is available at `http://127.0.0.1:8000/health`.

## Validate the frontend

```powershell
cd frontend
npm run build
npm test
```

## Firebase Authentication configuration

Copy `.env.example` to `.env` and fill in the Firebase web configuration for the frontend. Configure the backend Firebase Admin verification values with either `FIREBASE_SERVICE_ACCOUNT_JSON` or the individual `FIREBASE_PROJECT_ID`, `FIREBASE_CLIENT_EMAIL`, and `FIREBASE_PRIVATE_KEY` variables. Keep `.env` and service-account credentials local.

The protected backend identity endpoint is `GET /api/auth/me` and requires `Authorization: Bearer <Firebase ID token>`.

## Environment and secrets

Copy `.env.example` to `.env` for local configuration. `.env` is ignored by Git. Never commit credentials, service account files, or private API keys.

## Phase boundary

Phase 0, Phase 1, Phase 2, and Phase 3 are implemented. Lost/found workflows, image storage, Microsoft Foundry, OCR, embeddings, matching, claims, notifications, and admin workflows belong to later phases and are intentionally not included.