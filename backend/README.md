# Backend

FastAPI service for the University AI Lost & Found platform.

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
