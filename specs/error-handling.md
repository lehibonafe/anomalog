# Error handling

## Current taxonomy

| Class | Existing behavior | User impact / source |
| --- | --- | --- |
| HTTP input validation | FastAPI/Pydantic returns 422 detail; service `BadRequestError` returns 400 `{detail}` | Malformed body, invalid enum, range/limit/cursor/account-mode rejection. `schemas/`, `core/errors.py`. |
| HTTP abuse limit | Per-IP middleware returns 429 `{detail}` | Request throttled before route. `main.py`, `core/rate_limiter.py`. |
| Model quota | `LLMQuotaExceededError` returns 429 | First-chunk quota failure; later failure may become partial answer. `anomaly_service.py`. |
| Model request failure | `LLMRequestError` returns 502 | Provider failure; connection test often returns HTTP 200 with `success:false`. |
| Not found | `NotFoundError` maps to 404 | Defined in `core/errors.py`; no route-specific use found. |
| AWS/unhandled failure | May return FastAPI 500 | Discovery/search failure; no uniform AWS error mapping found. |
| External masker failure | Warning log, then local regex fallback | User can continue with reduced masking coverage. `masking.py`. |
| Live Tail protocol/runtime | WebSocket `error`, `session_stopped`, or `session_ended`; close 1008/1013 for listed cases | Stream ends; UI shows error or reason. `routes_cloudwatch.py`, `LiveTailControls.tsx`. |
| Database failure | **Not currently applicable** | No database exists. |
| Authentication/authorization failure | **Not currently applicable** in app | No app identity; AWS IAM denial may surface as AWS error. |

Provider adapters use bounded SDK timeouts and disable SDK retries; `AnomalyService` owns retries for rate-limit signals using exponential waits. The external masker uses an HTTP timeout and fail-fast fallback within a batch. AWS search routes do not declare an app-level timeout or retry strategy. Live Tail has an inactivity timeout and a bounded async queue. See [reliability.md](reliability.md).

Frontend search bars show 400 detail or a generic failure; pagination shows cursor-specific or retry text. The investigator supports retry and stop. Connection-test UI displays its returned message. Some backend exception strings are returned in diagnostics or WebSocket errors; review them for sensitive data before adding more detailed error reporting. This is a recommendation, not proof that current messages leak secrets.

## Future error-contract rule

When a behavior change adds an error, document its status/envelope in [api.md](api.md), its user-facing state in [frontend.md](frontend.md), and a focused test. Do not expose credentials or raw log messages in an error response.
