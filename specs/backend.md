# Backend

## Scope and ownership

The FastAPI service in `backend/app/` owns AWS and model access. `api/` declares routes, `schemas/` declares request and response shapes, `core/` holds AWS sessions, errors, and rate limiting, and `services/` holds search, masking, streaming, and LLM logic. Keep routes thin and put provider or AWS behavior in services.

The exact HTTP and WebSocket payloads live in [api-reference.md](../api-reference.md). Search, Live Tail, and analysis rules live in their feature specs; this file defines service-wide requirements.

## Required behavior

| Surface | Responsibility |
| --- | --- |
| `GET /api/health`, `GET /api/config` | Report service health and safe browser capabilities without returning credentials. |
| `POST /api/mask/test` | Run the local masker on supplied lines for development checks. |
| `GET /api/cloudwatch/log-groups` | Discover log groups with keyword filtering and continuation. |
| `POST /api/cloudwatch/logs/search` | Search selected groups with bounded, masked, ordered, cursor-based results. |
| `POST /api/cloudtrail/events/search` | Search centralized CloudTrail log groups or regional event history according to configuration. |
| `WS /api/cloudwatch/logs/live-tail` | Own one explicitly started AWS stream, mask events, and close on stop, disconnect, timeout, or backpressure. |
| `POST /api/analysis/anomalies`, `POST /api/analysis/test-connection` | Analyze submitted evidence or test the selected model destination. |

- Settings come from environment variables and `backend/.env`. The process uses the boto3 credential chain, optionally assumes `AWS_ROLE_ARN`, and uses `AWS_REGION` for clients. See [configuration.md](configuration.md) and [iam_setup.md](iam_setup.md).
- The backend enforces the configured maximum time range and positive search limits, caps search output with `MAX_LOG_SEARCH_LINES`, and returns clear client errors for rejected requests. It preserves event ordering and continuation semantics across pages and selected log groups.
- All log messages are masked before an HTTP or WebSocket response and are masked again before a provider call. The external masking service is used when configured; local masking handles its failure. Cursor-buffered messages remain masked.
- Provider calls respect configured analysis size, history, output, and retry limits. Analysis responses include coverage counts and warnings so omitted or partially processed evidence is visible.
- The HTTP rate limiter applies per client IP and per process. Live Tail concurrency is also per process; neither limit is a global cluster limit. WebSocket origins follow `CORS_ORIGINS`.
- API errors use the documented status and `detail` response. Do not include AWS credentials, model keys, or raw unmasked log messages in responses or error text.

## Acceptance checks

- `cd backend && .venv/bin/python -m pytest tests/` succeeds without live AWS or model calls.
- Changes to routes or schemas update [api-reference.md](../api-reference.md); changes to behavior update the relevant feature spec and service tests.
- Regression tests cover validation, masking, cursor continuation, CloudTrail mode selection, Live Tail closure, and provider failures where affected.
