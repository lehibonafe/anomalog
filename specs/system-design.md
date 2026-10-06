# System design

## Module map

| Layer | Important modules | Responsibility |
| --- | --- | --- |
| Browser composition | `frontend/src/App.tsx`, `components/` | Single-page layout, search controls, viewer, dashboard, investigator. |
| Browser request/state | `frontend/src/api/`, `hooks/`, `state/selectionStore.ts`, `state/queryClient.ts` | Typed HTTP calls, React Query request state, Zustand selection/events, stale-response guards. |
| HTTP/WebSocket boundary | `backend/app/main.py`, `api/routes_*.py`, `schemas/` | Routes, Pydantic shapes, CORS, HTTP rate limit, WebSocket protocol. |
| AWS access | `core/aws_session.py`, `services/cloudwatch_service.py`, `cloudtrail_service.py`, `live_tail_service.py` | Credentials, discovery, search, event conversion, Live Tail. |
| Pagination | `services/group_pagination.py` | Merge selected groups and serialize continuation state. |
| Privacy and analysis | `services/masking.py`, `core/masking_http_client.py`, `services/anomaly_service.py`, `services/log_filter.py`, `services/llm/` | Masking, evidence selection, budgets, provider calls. |

## Request lifecycle and state

Synchronous search routes call boto3 through services and return Pydantic response objects. Search services apply time/limit checks, read AWS, mask text, and issue cursors. Anomaly analysis is async: it re-masks submitted messages, selects evidence, compacts duplicates and JSON, chunks prompt input, paces calls by provider, and consolidates answers. `get_settings`, AWS sessions, masking client, and `get_anomaly_service` are cached per process with `lru_cache`.

React Query holds request state and log-group/config query caches; Zustand holds selected source, range, loaded events, pagination requests, model settings, and a generation counter. `LogSummary.tsx` alone persists completed chat turns in `localStorage`. There is no server-side user session or durable event store. See [data-model.md](data-model.md).

## Concurrency and failures

The HTTP rate limiter and provider RPM limiters are per process. A Live Tail WebSocket starts one daemon thread for the blocking AWS response stream and bridges events into a bounded async queue of 50 messages. The session limiter is also per process. A slow consumer, disconnect, stop, or inactivity sets the stop event and closes the stream. The browser caps paused events at 5,000 and displayed Live Tail history at 10,000.

External masking is attempted in batches when configured; failure falls back to local regex masking. Model quota/request failures can yield partial answers with warnings. Connection testing returns a normal response with `success: false` for many provider failures. See [error-handling.md](error-handling.md).

## Design rationale visible in source

Comments explicitly explain `lru_cache` for shared per-process pacing, the Live Tail worker thread for boto3's blocking stream, cursor buffering for cross-group order, and re-masking for callers that bypass search. Other architectural choices have no decision record in this checkout; treat their rationale as unknown rather than inferred. The cursor is compressed and query-bound but not cryptographically signed; this is an observed security risk, not an intended design guarantee ([security.md](security.md)).
