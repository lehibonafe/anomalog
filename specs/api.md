# Anomalog API

This file lists every route registered in `backend/app/main.py`: eight HTTP routes and one WebSocket route. All HTTP paths are under `/api`. When `ANOMALOG_API_KEY` is configured, every HTTP route except health and preflight requires `X-API-Key`; missing or wrong keys return 401. Live Tail requires the same header before its WebSocket handshake. Production refuses startup without a key. The shared key grants one machine access level, without per-user authorization. Every HTTP route may return 429 from the per-IP, per-process middleware; malformed Pydantic input normally returns FastAPI 422. Exact executable shapes come from `backend/app/schemas/`, route declarations, and `/openapi.json`; the [root API reference](../api-reference.md) provides examples.

### GET /api/health

**Purpose:** Shallow process health. **Authentication:** None. **Authorization:** None. **Request Parameters:** None. **Request Body:** None. **Response:** `{"status":"ok"}`. **HTTP Status Codes:** 200, middleware 429. **Validation:** None. **Possible Errors:** Unhandled server failure. **Side Effects:** None. Source: `backend/app/api/routes_meta.py`. A 200 does not verify AWS, masking, or model access.

### GET /api/config

**Purpose:** Expose browser-safe capabilities. **Authentication:** Shared X-API-Key when configured. **Authorization:** None. **Request Parameters:** None. **Request Body:** None. **Response:** `aws_region`, LiteLLM/Gemini configured booleans and model names, `max_log_search_lines`, `max_analysis_lines`, `cloudtrail_account_filter_available`, Live Tail concurrency/timeout/cost/free-tier values. **HTTP Status Codes:** 200, middleware 429. **Validation:** Settings are loaded at process startup. **Possible Errors:** Invalid server settings can prevent startup. **Side Effects:** None. No API keys are returned. Source: `routes_meta.py`.

### POST /api/mask/test

**Purpose:** Development diagnostic for local regex masking. **Authentication:** Shared X-API-Key when configured. **Authorization:** None. **Request Parameters:** None. **Request Body:** `{"lines": [string, ...]}`. **Response:** `{"masked": [string, ...]}` in input order. **HTTP Status Codes:** 200, 422, middleware 429, possible 500. **Validation:** `lines` must be a string array; no route-specific size cap is declared. **Possible Errors:** Pydantic validation or unhandled server error. **Side Effects:** None beyond CPU/memory. The external masker is not called. Source: `routes_meta.py`.

### GET /api/cloudwatch/log-groups

**Purpose:** Discover CloudWatch groups. **Authentication:** Shared X-API-Key when configured. **Authorization:** Backend AWS IAM. **Request Parameters:** optional `keyword`; optional compatibility alias `prefix` used only if `keyword` absent; optional `next_token`; `limit` integer 1–50, default 50. **Request Body:** None. **Response:** `log_groups[]` of `name`, `identifier`, optional `account_id`, `stored_bytes`, `creation_time`; `next_token`. **HTTP Status Codes:** 200, 422, middleware 429, possible 500 on AWS failure. **Validation:** FastAPI enforces limit. **Possible Errors:** AWS credentials, region, IAM, or AWS service failures. **Side Effects:** AWS read request. Source: `routes_cloudwatch.py`, `cloudwatch_service.py`.

### POST /api/cloudwatch/logs/search

**Purpose:** Search selected CloudWatch groups. **Authentication:** Shared X-API-Key when configured. **Authorization:** Backend AWS IAM. **Request Parameters:** None. **Request Body:** required `log_group_names: string[]`, `start_time`, `end_time`; optional `filter_pattern`, `cursor`; `limit` default 1000. **Response:** `events: LogEvent[]`, `cursor: string|null`, `truncated: boolean` (currently false), `total_returned: integer`. **HTTP Status Codes:** 200, 400 for service rejection, 422 for shape errors, middleware 429, possible 500 for AWS failure. **Validation:** Service enforces positive limit and `MAX_TIME_RANGE_DAYS`, caps page at `MAX_LOG_SEARCH_LINES`, and checks cursor/query match; the schema does not declare a nonempty group list or `start_time < end_time` constraint. **Possible Errors:** Invalid/oversized cursor, nonadvancing AWS pagination, IAM/region failure. **Side Effects:** AWS reads and optional external masking calls. Source: `routes_cloudwatch.py`, `cloudwatch_service.py`, `group_pagination.py`.

### POST /api/cloudtrail/events/search

**Purpose:** Search centralized CloudTrail groups or regional event history. **Authentication:** Shared X-API-Key when configured. **Authorization:** Backend AWS IAM. **Request Parameters:** None. **Request Body:** required `start_time`, `end_time`; optional `account_id` (six enum values in `schemas/cloudtrail.py`), `lookup_attribute_key`, `lookup_attribute_value`, `cursor`; `limit` default 1000. **Response:** Same search envelope as CloudWatch. **HTTP Status Codes:** 200, 400 for service rejection, 422 for shape errors, middleware 429, possible 500 for AWS failure. **Validation:** Positive limit and max range; account selection only with centralized groups; enum validation by Pydantic. **Possible Errors:** Missing linked group, invalid cursor, unsupported account mode, IAM/region failure. **Side Effects:** AWS read and optional external masking calls. Centralized output is oldest-first; regional lookup output newest-first. Source: `routes_cloudtrail.py`, `cloudtrail_service.py`.

### POST /api/analysis/anomalies

**Purpose:** Analyze submitted events. **Authentication:** Shared X-API-Key when configured. **Authorization:** None in app; provider credential may be needed. **Request Parameters:** None. **Request Body:** required `events: LogEvent[]`, `context.source_description`; optional `provider` (default `litellm`), `api_key`, `model`, `base_url`, `user_prompt`, `history[]` of `{role,content}`. **Response:** `analysis`, `references[]` (currently empty by default), chunk/line/coverage/token counts, `model`, `warnings[]`; see `schemas/analysis.py`. **HTTP Status Codes:** 200, 400 for service limits, unapproved base URL, or provider setup, 422 shape errors, 429 quota or middleware, 502 provider failure, possible 500. **Validation:** Event count ≤ `MAX_LOG_SEARCH_LINES`; history count ≤ `MAX_CHAT_HISTORY_MESSAGES`; base URL must match the provider default or its configured allowlist; evidence and history are trimmed by budgets. **Possible Errors:** Missing provider credential, quota, model/transport failure. **Side Effects:** Model calls; request messages are locally re-masked before provider use. Source: `routes_analysis.py`, `anomaly_service.py`.

### POST /api/analysis/test-connection

**Purpose:** Test selected model destination with a small synthetic prompt. **Authentication:** Shared X-API-Key when configured. **Authorization:** None in app; provider credential may be needed. **Request Parameters:** None. **Request Body:** optional `provider` (default `litellm`), `api_key`, `model`, `base_url`. **Response:** `{success:boolean,message:string,model:string}`. **HTTP Status Codes:** Usually 200 even when `success:false`; 422 for shape errors, middleware 429, possible 500 for unexpected setup failure. **Validation:** Provider enum, exact base URL allowlist, and SDK setup. **Possible Errors:** Missing key, unapproved or unreachable URL, upstream quota or refusal appear as `success:false` in normal response. **Side Effects:** One provider request if configuration is accepted; may incur provider cost. Source: `routes_analysis.py`, `anomaly_service.py`.

### WS /api/cloudwatch/logs/live-tail

**Purpose:** Proxy one CloudWatch Live Tail stream. **Authentication:** Shared X-API-Key when configured. **Authorization:** Backend AWS IAM; optional Origin check against `CORS_ORIGINS`. **Request Parameters:** None. **Request Body:** First JSON message within 10 seconds: `{type:"start",log_group_names:string[1..10],filter_pattern?:string|null}` with pattern ≤1024 characters; then `{type:"activity"}` or `{type:"stop"}`. **Response:** JSON messages `session_started` (timeout/cost estimates), `events` (masked event array and `sampled`), `session_stopped`, `session_ended`, or `error`. **HTTP Status Codes:** WebSocket upgrade/close codes rather than ordinary HTTP JSON statuses; forbidden Origin closes 1008, session limit closes 1013. **Validation:** First-message Pydantic model, nonblank unique group names, per-process session limit. **Possible Errors:** Invalid start, AWS failure, slow consumer, inactivity, disconnect. **Side Effects:** Starts a billable AWS stream only after a valid start message; closes stream on terminal conditions. Source: `routes_cloudwatch.py`, `live_tail_service.py`.

## External APIs called by Anomalog

| External operation | Caller | Purpose |
| --- | --- | --- |
| CloudWatch Logs `DescribeLogGroups`, `FilterLogEvents`, `StartLiveTail` | `cloudwatch_service.py`, `cloudtrail_service.py`, `live_tail_service.py` | Discovery, search, stream. |
| CloudTrail `LookupEvents` | `cloudtrail_service.py` | Regional fallback. |
| STS `AssumeRole` | `core/aws_session.py` through botocore | Optional monitoring-account identity. |
| `POST /api/mask/structured/` on configured masking service | `services/masking.py` | Batch masking; its separate API is in [root masking reference](../api-reference-pii-masking.md). |
| LiteLLM/OpenAI-compatible, Gemini, Anthropic, Ollama provider APIs | `services/llm/*_provider.py` | Analysis and connection diagnostics. |

External service versions and quotas can change; validate them against provider documentation during integration work. They are not additional Anomalog routes.
