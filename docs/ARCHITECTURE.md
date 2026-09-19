# Phase 0 Architecture Boundary

The repository currently contains two independently runnable applications:

- `frontend/`: React, Vite, and TypeScript client
- `backend/`: FastAPI service with `GET /health`, Firebase-protected identity access, and Phase 2 student profile endpoints

Phase 2 stores student profiles in SQLite. Each profile is keyed by the verified Firebase UID supplied by the backend auth dependency.

Phase 3 adds the foundational `users`, `lost_items`, `found_items`, `matches`, `claims`, and `audit_events` tables. The schema includes foreign keys, status constraints, indexes, repeatable initialization, and transaction-backed repository primitives. Feature workflows remain out of scope until their later phases.

Phase 4 adds owner-scoped lost-item CRUD APIs and a frontend report form. Phase 5 adds protected Firebase Storage uploads; lost-item records store only generated storage references, never image binaries. Client-side Storage access is denied by `storage.rules`; the backend Admin SDK is the storage path.

Found-item workflows, AI, matching, claims, notifications, and administration belong to later phases and are intentionally absent from this foundation.
