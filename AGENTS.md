# Repository Guidelines

## Project Structure & Module Organization

Anomalog has two independently developed services. `backend/app/` contains the FastAPI application: routes live in `api/`, request and response models in `schemas/`, AWS and rate-limit helpers in `core/`, and business logic plus LLM adapters in `services/`. Backend tests mirror these areas under `backend/tests/`. `frontend/src/` contains the React/TypeScript UI, organized into `components/`, `hooks/`, `api/`, `state/`, `utils/`, and `assets/`. Root scripts and `docker-compose.yml` coordinate both services.

## Build, Test, and Development Commands

- `./dev.sh`: start uvicorn on port 8000 and Vite on port 5173; requires the backend virtual environment and installed frontend packages.
- `cd backend && python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`: create the Python environment.
- `cd backend && python -m pytest tests/`: run all backend tests.
- `cd frontend && npm install && npm run dev`: install dependencies and start the UI.
- `cd frontend && npm run build`: type-check and produce the Vite bundle.
- `cd frontend && npm run lint`: run ESLint.
- `docker compose up --build`: run both services with hot reload.

Copy each service's `.env.example` to `.env` before local use. Never commit API keys or AWS credentials.

## Coding Style & Naming Conventions

Use four-space indentation and `snake_case` for Python functions, modules, and tests; use `PascalCase` for classes. Keep FastAPI routes thin and place provider/AWS logic in services. TypeScript uses two-space indentation, single quotes, `camelCase` for functions and hooks, and `PascalCase` for React components and `.tsx` filenames. Follow the existing ESLint configuration and keep API types in `frontend/src/api/types.ts`.

## Testing Guidelines

Backend tests use pytest with async support. Name files `test_<feature>.py` and tests `test_<behavior>`. Run pytest as `python -m pytest` from `backend/`; target a case with `python -m pytest tests/test_log_filter.py::test_name`. Mock AWS and LLM SDK calls—tests must not make live requests. Add regression coverage for service, masking, pagination, and provider changes. Frontend utility tests use Vitest; run `npm run test`, `npm run lint`, and `npm run build` for UI changes.

## Specification Workflow

Read the relevant file in `specs/` before changing behavior, update its requirements and acceptance checks as part of the change, then implement and verify. Keep the root `api-reference.md` in sync with backend routes and schemas; the existing `api-reference_1.md` documents a separate masking service.

## Commit & Pull Request Guidelines

History uses short, imperative summaries such as `add APM dashboard` and `improve prompt`. Keep commits focused and make the subject describe the outcome. Pull requests should explain behavior and configuration changes, list verification commands, link related issues, and include screenshots for UI work. Highlight security-sensitive changes involving masking, credentials, CORS, or network exposure.
