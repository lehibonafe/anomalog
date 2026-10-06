# Anomalog API reference

This reference describes **Anomalog's own FastAPI service**. The existing [api-reference_1.md](api-reference_1.md) describes the separate external PII masking service. For the exact generated schema of a running Anomalog instance, use `/openapi.json` or `/docs`.

## Base URL and conventions

- Local HTTP base: `http://localhost:8000`; all application routes start with `/api`.
- JSON request and response bodies use `snake_case`. Timestamps are ISO 8601 date-times with a timezone, for example `2026-10-06T10:00:00Z`.
- The service has no application authentication. Restrict access at the network or reverse-proxy layer. The HTTP rate limit is per client IP and backend process (default 120 requests/minute). A rate-limited request returns HTTP `429` with `{"detail":"Too many requests. Slow down and try again shortly."}`.
- Pydantic validation failures use FastAPI's HTTP `422` detail format. Application errors use `{"detail":"message"}` (usually `400`, `404`, `429`, or `502`). AWS and other unhandled failures may return `500`.
- Search cursors and AWS next tokens are opaque. Send the returned value unchanged with the same search inputs; `null` means there is no next page.
- Search and Live Tail event messages are masked before delivery. The analysis route re-masks submitted messages before an LLM call. `/api/mask/test` uses only the local regex masker.

## Common event object

```json
{
  "source": "cloudwatch",
  "origin": "/aws/lambda/example",
  "stream_or_key": "2026/10/06/[$LATEST]abc",
  "timestamp": "2026-10-06T10:00:00Z",
  "message": "ERROR request failed",
  "line_index": 0
}
```

`source` is `cloudwatch` or `cloudtrail`; `timestamp` may be `null`. `line_index` is an integer assigned within a search response. The UI gives every appended event a unique increasing index, including events in a Live Tail batch. For CloudTrail, `stream_or_key` is the event name and `origin` identifies CloudTrail or the centralized account/region.

## Health, configuration, and masking

| Method | Path | Request | Response |
| --- | --- | --- | --- |
| `GET` | `/api/health` | None | `{"status":"ok"}` |
| `GET` | `/api/config` | None | Public runtime configuration described below |
| `POST` | `/api/mask/test` | `{"lines":["text"]}` | `{"masked":["masked text"]}` |

`GET /api/config` returns `aws_region`, `litellm_configured`, `litellm_model`, `gemini_configured`, `gemini_model`, `max_log_search_lines`, `max_analysis_lines`, `cloudtrail_account_filter_available`, `live_tail_max_concurrent_sessions`, `live_tail_inactivity_timeout_seconds`, `live_tail_cost_per_minute_usd`, and `live_tail_free_tier_minutes`. The configured flags are booleans; no keys are returned. `cloudtrail_account_filter_available` is true when centralized groups or linked-account discovery is configured.

`POST /api/mask/test` is reachable on deployed instances unless the deployment blocks it. It applies local regex masking to each posted line; it does not call the external masker.

## CloudWatch Logs

### `GET /api/cloudwatch/log-groups`

Query parameters:

| Name | Type | Default | Meaning |
| --- | --- | --- | --- |
| `keyword` | string | omitted | AWS log-group name pattern |
| `prefix` | string | omitted | Compatibility alias used if `keyword` is absent |
| `next_token` | string | omitted | Token from the previous response |
| `limit` | integer, 1–50 | `50` | Groups to request from AWS |

Response:

```json
{
  "log_groups": [{
    "name": "/aws/lambda/example",
    "identifier": "arn:aws:logs:ap-southeast-1:123456789012:log-group:/aws/lambda/example",
    "account_id": "123456789012",
    "stored_bytes": 12345,
    "creation_time": "2026-10-01T00:00:00Z"
  }],
  "next_token": null
}
```

`account_id`, `stored_bytes`, and `creation_time` may be `null` when AWS omits them. Linked-account discovery depends on server configuration.

### `POST /api/cloudwatch/logs/search`

Request:

```json
{
  "log_group_names": ["/aws/lambda/example"],
  "start_time": "2026-10-06T09:00:00Z",
  "end_time": "2026-10-06T10:00:00Z",
  "filter_pattern": "ERROR",
  "limit": 1000,
  "cursor": null
}
```

`log_group_names`, `start_time`, and `end_time` are required. Group names or ARNs are accepted. `filter_pattern` and `cursor` default to `null`; `limit` defaults to `1000`, must be positive, and is capped by `MAX_LOG_SEARCH_LINES` (default `5000`). The maximum time span is `MAX_TIME_RANGE_DAYS` (default seven days).

Response: `{"events":[LogEvent],"cursor":string|null,"truncated":false,"total_returned":integer}`. Events from selected groups are oldest-first across response pages. A cursor is bound to its original groups, time range, and filter; send it unchanged with those same request fields. Cursors issued before the merged pagination format must be replaced by a new search. AWS can return an empty page with a continuation cursor. `truncated` is currently always `false`; use `cursor` to determine whether more pages are available.

## CloudTrail

### `POST /api/cloudtrail/events/search`

Request:

```json
{
  "start_time": "2026-10-06T09:00:00Z",
  "end_time": "2026-10-06T10:00:00Z",
  "account_id": null,
  "lookup_attribute_key": "EventName",
  "lookup_attribute_value": "StopInstances",
  "limit": 1000,
  "cursor": null
}
```

Only the timestamps are required. Optional `lookup_attribute_key` values are `EventId`, `EventName`, `ReadOnly`, `Username`, `ResourceType`, `ResourceName`, `EventSource`, and `AccessKeyId`. `account_id` can be one of `887350548529`, `065031412132`, `221315724874`, `550222016520`, `679437835821`, or `765186506449`; it requires centralized CloudWatch log groups. The lookup value is a string. `limit` defaults to `1000`, is capped by `MAX_LOG_SEARCH_LINES`, and must be positive. The maximum time span is `MAX_TIME_RANGE_DAYS`.

The backend searches centralized CloudWatch groups if explicitly configured or if linked-account discovery is enabled; otherwise it calls regional CloudTrail `LookupEvents`. Centralized results are oldest-first across pages; regional event history is newest-first across pages, matching `LookupEvents`. The latter API reads pages of at most 50 events, so a response can contain fewer than the requested limit. Response shape matches CloudWatch search: `events`, `cursor`, `truncated`, and `total_returned`.

## AI analysis

### `POST /api/analysis/anomalies`

Request:

```json
{
  "events": [{
    "source": "cloudwatch",
    "origin": "/aws/lambda/example",
    "stream_or_key": "stream",
    "timestamp": "2026-10-06T10:00:00Z",
    "message": "ERROR request failed",
    "line_index": 0
  }],
  "context": {"source_description": "Example log group"},
  "provider": "litellm",
  "user_prompt": "What failed?",
  "history": []
}
```

`events` and `context.source_description` are required. `provider` defaults to `litellm` and also accepts `gemini`, `openai`, `anthropic`, and `ollama`. Optional `api_key`, `model`, `base_url`, and `user_prompt` may be omitted or `null`. `history` defaults to `[]` and contains `{ "role": "user" | "assistant", "content": "..." }`. The backend rejects more than `MAX_LOG_SEARCH_LINES` input events or `MAX_CHAT_HISTORY_MESSAGES` history messages. Provider calls are subject to server limits and rate pacing.

Response fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `analysis` | string | Model answer or available partial batch answers |
| `references` | array of `{start,end}` | Line ranges; currently defaults to an empty array |
| `chunks_analyzed`, `chunks_total` | integer | Completed and planned chunks |
| `lines_submitted`, `lines_analyzed`, `lines_sent_to_model` | integer | Input, covered, and compact evidence line counts |
| `lines_collapsed_as_duplicates`, `lines_omitted_by_limits`, `lines_not_analyzed`, `lines_shortened` | integer | Processing diagnostics |
| `lines_considered`, `lines_skipped_by_prefilter` | integer | Retrieval diagnostics |
| `history_messages_omitted`, `estimated_input_tokens` | integer | Conversation and token estimates |
| `model` | string | Effective model |
| `warnings` | string array | Partial failures or processing limits |

### `POST /api/analysis/test-connection`

Request: `{"provider":"litellm","api_key":null,"model":null,"base_url":null}`. The same provider names and optional settings apply as above. Response: `{"success":true,"message":"Connected successfully.","model":"effective-model"}`. A provider connection or configuration failure is normally returned as HTTP `200` with `success:false` and a diagnostic `message`.

## CloudWatch Live Tail WebSocket

Connect to `ws://localhost:8000/api/cloudwatch/logs/live-tail` (or `wss://` under HTTPS). The first client message must arrive within 10 seconds:

```json
{"type":"start","log_group_names":["/aws/lambda/example"],"filter_pattern":"ERROR"}
```

The group list must contain 1–10 nonblank names or ARNs. `filter_pattern` is optional, maximum 1024 characters. While connected, send `{"type":"activity"}` to refresh the inactivity timer or `{"type":"stop"}` to stop. The browser UI sends activity at most once every 30 seconds. Origin validation uses `CORS_ORIGINS`; the session limit is per backend process.

Server messages:

| Type | Fields | Meaning |
| --- | --- | --- |
| `session_started` | `inactivity_timeout_seconds`, `cost_per_minute_usd`, `free_tier_minutes` | AWS started the session; cost fields are display estimates |
| `events` | `events: LogEvent[]`, `sampled: boolean` | Masked log batch |
| `session_stopped` | `reason` | User or inactivity stopped the session |
| `session_ended` | `reason` | AWS ended the session |
| `error` | `message` | Invalid start, session limit, AWS, or streaming error |

The WebSocket may close after a terminal message. There is no historical pagination on this stream.
