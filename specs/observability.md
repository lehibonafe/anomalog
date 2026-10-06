# Observability

## Existing signals

`GET /api/health` returns `{"status":"ok"}` when the FastAPI process can answer; it does not check AWS, masking, or model dependencies (`backend/app/api/routes_meta.py`). `GET /api/config` reveals safe capability flags and operating limits, not dependency status. Uvicorn provides normal server/access output when run; `backend/app/core/masking_http_client.py` and `backend/app/services/masking.py` issue Python logging warnings for disabled TLS verification and masking fallback. No structured application request logging, metrics endpoint, tracing instrumentation, alert rules, dashboard configuration, or centralized log shipping is present in this checkout.

The UI shows per-session Live Tail elapsed time, event count, estimated cost, sampling, and dropped events (`LiveTailControls.tsx`). These are user-facing session signals, not exported operational telemetry. Analysis responses include line/chunk coverage and warnings; no server-side metric exporter consumes them.

## Operational questions and recommended signals

| Dimension | Current evidence | Recommendation, not implemented |
| --- | --- | --- |
| Availability | Shallow `/api/health` | Probe API and browser from outside deployment; separate readiness from liveness. |
| Latency | No measured series | Record p50/p95 search, masker, analysis, and WebSocket startup latency without logging raw prompts or events. |
| Traffic | No aggregate counter | Count search, analysis, connection-test, and Live Tail starts by outcome. |
| Errors | HTTP errors and masking warnings | Count AWS/LLM/masker failures, 4xx/5xx, stream termination reasons; redact logs. |
| Saturation | Per-process limits only | Observe active Live Tail sessions, queue overflow, provider pacing waits, worker count, memory, and CPU. |

No formal SLI/SLO or error budget exists. **Proposed SLIs**, without target values: successful health checks / total checks; successful bounded AWS searches / valid search attempts; analysis responses with at least one completed chunk / valid analysis attempts; unexpected Live Tail terminations / started sessions. Product and operations owners must approve windows and target values before they become requirements. See [reliability.md](reliability.md).
