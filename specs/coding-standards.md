# Coding standards

These conventions come from `AGENTS.md` and checked-in source. They are repository guidance, not a new style migration.

| Area | Existing convention |
| --- | --- |
| Python | Four-space indentation; `snake_case` functions/modules/tests, `PascalCase` classes; route handlers in `backend/app/api/`, Pydantic models in `schemas/`, AWS/provider logic in `services/` and `core/`. |
| TypeScript/React | Two-space indentation preferred by `AGENTS.md`; `camelCase` functions/hooks and `PascalCase` components/`.tsx` names; single quotes preferred, though existing files mix quote/semicolon styles. Follow local file style and ESLint. |
| API | JSON `snake_case` fields; FastAPI route prefix `/api`; shared `LogEvent`; keep backend schemas and `frontend/src/api/types.ts` aligned. |
| Errors | Use `AppError` subclasses for intentional HTTP status/detail; preserve diagnostic response contract for connection test. |
| Configuration | Put defaults/validation in `backend/app/config.py`; document new variables in `.env.example` and [configuration.md](configuration.md); do not commit `.env`. |
| Dependencies | Python declarations in `backend/requirements.txt`; npm dependencies and lockfile in `frontend/package.json`/`package-lock.json`. |
| Tests | `backend/tests/test_<feature>.py` and `test_<behavior>` functions; frontend `*.test.ts` with Vitest; mock AWS and model calls. |
| Logging | Python `logging` appears in masking helpers; avoid logging raw messages, keys, or request bodies. No general structured-logging standard exists yet. |
| Database | **Not currently applicable**; no database schema/migration convention exists. |

Run the commands in [testing.md](testing.md). For behavior changes, update [requirements.md](requirements.md), the relevant feature spec, and [api.md](api.md) when the wire contract changes. `api-reference-pii-masking.md` documents a separate service and must not be treated as Anomalog route source.
