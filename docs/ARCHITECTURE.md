# Phase 0 Architecture Boundary

The repository currently contains two independently runnable applications:

- `frontend/`: React, Vite, and TypeScript client
- `backend/`: FastAPI service with `GET /health`, Firebase-protected identity access, and Phase 2 student profile endpoints

Phase 2 stores only student profiles in SQLite. Each profile is keyed by the verified Firebase UID supplied by the backend auth dependency.

Lost/found application data, storage, AI, matching, claims, notifications, and administration belong to later phases and are intentionally absent from this foundation.
