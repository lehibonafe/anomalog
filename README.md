# Anomalog

Local web app for investigating AWS CloudWatch Logs and S3-stored logs by source
and time range, with Google Gemini (free tier) anomaly/error highlighting over
the filtered slice.

## Architecture

- `backend/` — FastAPI service. Talks to AWS (boto3) and Gemini (`google-genai`).
- `frontend/` — React + TypeScript (Vite) UI.

The backend uses boto3's default credential chain, checked in this order:
`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` env vars (e.g. `export`ed in your
shell) → the `AWS_PROFILE` named profile from `~/.aws/credentials` (only if
set in `backend/.env`; it's blank by default) → the instance/task IAM role
when deployed onto AWS compute. Leave `AWS_PROFILE` blank if you export keys
directly — setting it forces boto3 to use that profile instead, ignoring
exported env vars.

Gemini's free tier has real rate/quota limits, so before any log slice is sent
to the model the backend prefilters for errors/exceptions/stack traces, caps
total lines/characters, and chunks + paces requests (see
`backend/app/services/log_filter.py` and `gemini_service.py`).

## Setup

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in GEMINI_API_KEY
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
```

## Running

Two terminals:

```bash
# terminal 1
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000

# terminal 2
cd frontend && npm run dev
```

Or from the repo root, run both at once:

```bash
./dev.sh
```

Then open http://localhost:5173.

### Or with Docker

```bash
docker compose up --build
```

Runs both services in dev mode with hot reload — `backend/app` and
`frontend/src` are bind-mounted into their containers, so local edits apply
without rebuilding. The backend container mounts your host `~/.aws` read-only
(for profile-based auth) and also passes through `AWS_ACCESS_KEY_ID`/
`AWS_SECRET_ACCESS_KEY`/`AWS_SESSION_TOKEN` from your shell if you `export`ed
them before running `docker compose up` — same credential chain as running
locally. Requires `backend/.env` and `frontend/.env` to already exist (see
Setup above).

Then open http://localhost:5173.

## Tests

```bash
cd backend && source .venv/bin/activate
python -m pytest tests/
```
