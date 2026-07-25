<!-- Last Updated: 2026-04-15 -->

# API Reference — LLM Masking Service

## Table of Contents

1. [Introduction](#1-introduction)
2. [Authentication](#2-authentication)
3. [Error Handling](#3-error-handling)
4. [Rate Limiting](#4-rate-limiting)
5. [Auth Endpoints](#5-auth-endpoints)
6. [Admin Endpoints](#6-admin-endpoints)
7. [API Key Endpoints](#7-api-key-endpoints)
8. [PII Masking Endpoints](#8-pii-masking-endpoints)
9. [Session Endpoints](#9-session-endpoints)
10. [LLM Provider Key Endpoints](#10-llm-provider-key-endpoints)
11. [Pipeline Endpoint](#11-pipeline-endpoint)
12. [Webhook Endpoint](#12-webhook-endpoint)
13. [OpenAI-Compatible Proxy](#13-openai-compatible-proxy)
14. [Pattern Endpoints](#14-pattern-endpoints)
15. [PII Masking Reference](#15-pii-masking-reference)
16. [Workflow Examples](#16-workflow-examples)

---

## 1. Introduction

The LLM Masking Service is a Django REST Framework API that acts as a privacy layer between your applications and LLM providers (OpenAI, Anthropic, Gemini). Before text reaches an LLM, the service detects and replaces PII with structured placeholders. After the LLM responds, the service restores the original values.

**Base URLs**

| Environment | URL |
|-------------|-----|
| Local development | `http://localhost:8000` |
| Production | `https://your-domain.com` |

**Content-Type:** All requests and responses use `application/json` unless otherwise noted. The OpenAI-compatible proxy streaming endpoint returns `text/event-stream` when `stream: true` is requested.

**Versioning:** The API does not currently use a URL version prefix for most endpoints (e.g. `/api/mask/`). The OpenAI-compatible proxy endpoint is an exception: it lives under `/api/v1/` to match the OpenAI SDK's expected path.

---

## 2. Authentication

The service supports two authentication methods. Every request must supply exactly one of them, except for the public login and token-refresh endpoints.

### 2.1 JWT Bearer Token

Obtain a short-lived access token (15-minute lifetime) by posting credentials to `/api/auth/login/`. Include the token in subsequent requests using the `Authorization` header.

```
Authorization: Bearer <access_token>
```

When the access token expires, exchange your refresh token (7-day lifetime) at `/api/auth/refresh/` for a new access token without re-entering credentials.

**Obtaining tokens**

```bash
curl -s -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "secret"}' \
  | jq '{access, refresh}'
```

### 2.2 API Key

Long-lived API keys are created at `/api/keys/` while authenticated via JWT. Once created, use the key directly in the `X-API-Key` header. The raw key is only returned once at creation time; store it securely.

```
X-API-Key: pii_<token>
```

Keys are bcrypt-hashed in the database. The service uses prefix-based lookup (first 12 characters) for performance, then verifies the full key hash. Each use updates the `last_used_at` timestamp.

**When to use each method**

- JWT is appropriate for interactive user sessions and short-lived scripts.
- API keys are appropriate for automation, n8n workflows, CI pipelines, and any long-running service that cannot refresh tokens.

---

## 3. Error Handling

All error responses follow a consistent JSON envelope:

```json
{
  "detail": "Human-readable error message."
}
```

Validation errors (400) return field-level detail:

```json
{
  "field_name": ["Error message for this field."],
  "non_field_errors": ["Cross-field validation message."]
}
```

The OpenAI-compatible proxy uses OpenAI's error envelope format instead:

```json
{
  "error": {
    "message": "Description of the error.",
    "type": "invalid_request_error",
    "code": "unknown_model"
  }
}
```

**HTTP Status Codes**

| Code | Meaning |
|------|---------|
| 200 | OK — request succeeded |
| 201 | Created — resource was created |
| 204 | No Content — resource was deleted |
| 400 | Bad Request — validation failed, missing field, or bad input (e.g. no active provider key) |
| 401 | Unauthorized — authentication credentials are missing or invalid |
| 403 | Forbidden — authenticated but insufficient permission for this resource |
| 404 | Not Found — resource does not exist, or belongs to another user |
| 410 | Gone — session has expired (TTL elapsed) |
| 429 | Too Many Requests — per-user rate limit exceeded (pipeline or webhook) |
| 502 | Bad Gateway — the upstream LLM provider returned an error |

---

## 4. Rate Limiting

The pipeline endpoint (`POST /api/pipeline/`) and the webhook endpoint (`POST /api/webhook/mask-and-forward/`) apply a rate limit. The limit is **60 requests per minute per authenticated user** (configurable via the `WEBHOOK_THROTTLE_RATE` environment variable; default `60/minute`).

Both endpoints share the same per-user `user` throttle scope, so the 60/minute budget is counted across the two combined — not a separate allowance for each.

When the limit is exceeded the service returns HTTP 429 with no body. Callers should implement exponential backoff.

All other endpoints are not rate-limited at the application layer. Network-level rate limiting (e.g. nginx) is outside the scope of this document.

---

## 5. Auth Endpoints

### POST /api/auth/login/

Authenticate with username and password. Returns a JWT access token and a refresh token.

**Auth required:** None (public endpoint)

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `username` | string | Yes | The user's username |
| `password` | string | Yes | The user's password |

**Response (200)**

```json
{
  "access": "<JWT access token, expires in 15 minutes>",
  "refresh": "<JWT refresh token, expires in 7 days>"
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | Invalid username or password |

**curl example**

```bash
curl -s -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "secret"
  }'
```

---

### POST /api/auth/refresh/

Exchange a refresh token for a new access token.

**Auth required:** None (public endpoint)

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `refresh` | string | Yes | A valid, unexpired JWT refresh token |

**Response (200)**

```json
{
  "access": "<new JWT access token>"
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | Refresh token is invalid or expired |

**curl example**

```bash
curl -s -X POST http://localhost:8000/api/auth/refresh/ \
  -H "Content-Type: application/json" \
  -d '{
    "refresh": "<your_refresh_token>"
  }'
```

---

### GET /api/auth/me/

Return the authenticated user's profile.

**Auth required:** JWT or API Key

**Request body:** None

**Response (200)**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "alice",
  "full_name": "Alice Smith",
  "is_active": true,
  "is_superuser": false,
  "created_at": "2025-01-15T10:00:00Z"
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | No valid auth credentials provided |

**curl example**

```bash
curl -s http://localhost:8000/api/auth/me/ \
  -H "Authorization: Bearer $TOKEN"
```

---

## 6. Admin Endpoints

All admin endpoints require the requesting user to have `is_staff = true` (Django's `IsAdminUser` permission). Superusers automatically satisfy this requirement.

### GET /api/admin/users/

List all users in the system, ordered by creation date (newest first).

**Auth required:** JWT or API Key + `is_staff`

**Request body:** None

**Response (200)** — array of user objects

```json
[
  {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "username": "alice",
    "full_name": "Alice Smith",
    "is_active": true,
    "is_staff": false,
    "is_superuser": false,
    "created_at": "2025-01-15T10:00:00Z"
  }
]
```

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | Not authenticated |
| 403 | Authenticated but not staff |

**curl example**

```bash
curl -s http://localhost:8000/api/admin/users/ \
  -H "Authorization: Bearer $TOKEN"
```

---

### POST /api/admin/users/

Create a new user account.

**Auth required:** JWT or API Key + `is_staff`

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `username` | string | Yes | Unique username |
| `password` | string | Yes | Minimum 8 characters |
| `full_name` | string | No | Display name (default: `""`) |
| `is_active` | boolean | No | Whether the account is enabled (default: `true`) |
| `is_staff` | boolean | No | Whether the user has admin access (default: `false`) |
| `is_superuser` | boolean | No | Whether the user has full superadmin privileges (default: `false`) |

**Response (201)**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440001",
  "username": "bob",
  "full_name": "Bob Jones",
  "is_active": true,
  "is_staff": false,
  "is_superuser": false
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Username already exists or password too short |
| 401 | Not authenticated |
| 403 | Authenticated but not staff |

**curl example**

```bash
curl -s -X POST http://localhost:8000/api/admin/users/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "bob",
    "password": "securepass123",
    "full_name": "Bob Jones",
    "is_active": true
  }'
```

---

### PATCH /api/admin/users/{id}/

Update a user's status flags. Only `is_active`, `is_staff`, and `is_superuser` can be changed via this endpoint.

**Auth required:** JWT or API Key + `is_staff`

**Path parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | UUID | The user's UUID |

**Request body** (all fields optional)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `is_active` | boolean | No | Enable or disable the account |
| `is_staff` | boolean | No | Grant or revoke admin access |
| `is_superuser` | boolean | No | Grant or revoke superuser privileges |

**Response (200)**

```json
{
  "is_active": false,
  "is_staff": false,
  "is_superuser": false
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Invalid field values |
| 401 | Not authenticated |
| 403 | Authenticated but not staff |
| 404 | User not found |

**curl example**

```bash
curl -s -X PATCH http://localhost:8000/api/admin/users/550e8400-e29b-41d4-a716-446655440001/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'
```

---

## 7. API Key Endpoints

API keys let callers authenticate without a JWT. Each key is scoped to the creating user and bcrypt-hashed in the database. The raw key string (`pii_<token>`) is only returned once, at creation time.

### GET /api/keys/

List all API keys belonging to the authenticated user.

**Auth required:** JWT or API Key

**Request body:** None

**Response (200)** — array of key metadata objects (raw key value is never returned for existing keys)

```json
[
  {
    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "label": "n8n automation",
    "last_used_at": "2025-03-01T14:22:00Z",
    "expires_at": null,
    "is_active": true,
    "created_at": "2025-01-20T09:00:00Z",
    "raw_key": null
  }
]
```

**curl example**

```bash
curl -s http://localhost:8000/api/keys/ \
  -H "Authorization: Bearer $TOKEN"
```

---

### POST /api/keys/

Create a new API key for the authenticated user. The `raw_key` field in the response is the only time the full key value is returned; store it immediately.

**Auth required:** JWT or API Key

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `label` | string | No | Human-readable label for identifying this key (default: `""`) |

**Response (201)**

```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "label": "n8n automation",
  "last_used_at": null,
  "expires_at": null,
  "is_active": true,
  "created_at": "2025-04-15T12:00:00Z",
  "raw_key": "pii_AbCdEfGhIjKlMnOpQrStUvWxYz1234567"
}
```

> **Note:** The `raw_key` field is present only in the creation response. Subsequent `GET /api/keys/` calls return `null` for this field. If you lose the key, delete it and create a new one.

**curl example**

```bash
curl -s -X POST http://localhost:8000/api/keys/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"label": "n8n automation"}'
```

---

### DELETE /api/keys/{id}/

Revoke (permanently delete) an API key. Any in-flight requests using this key will fail immediately with 401.

**Auth required:** JWT or API Key

**Path parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | UUID | The API key's UUID |

**Response:** 204 No Content

**Error responses**

| Code | Condition |
|------|-----------|
| 404 | Key not found or belongs to a different user |

**curl example**

```bash
curl -s -X DELETE http://localhost:8000/api/keys/a1b2c3d4-e5f6-7890-abcd-ef1234567890/ \
  -H "Authorization: Bearer $TOKEN"
```

---

## 8. PII Masking Endpoints

These endpoints expose the core masking and unmasking operations. A **session** is created on each mask call; it stores the encrypted original text and the placeholder-to-original mapping. The session ID is required for unmasking.

### POST /api/mask/

Mask PII in a plain text string. Returns a session ID and the masked text with PII replaced by placeholders.

**Auth required:** JWT or API Key

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | Yes | The input text containing potential PII |
| `mode` | string | Yes | `"pipeline"` or `"webchat"` — used to categorize the session |

**Response (200)**

```json
{
  "session_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "masked_text": "My name is [PERSON_1] and my email is [EMAIL_ADDRESS_1]."
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Missing required field or invalid `mode` value |
| 401 | Not authenticated |

**curl example**

```bash
curl -s -X POST http://localhost:8000/api/mask/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "My name is Alice Smith and my email is alice@example.com.",
    "mode": "pipeline"
  }'
```

---

### POST /api/unmask/

Replace placeholders in an LLM response with the original PII values from the session.

**Auth required:** JWT or API Key

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | UUID | Yes | The session ID returned by `/api/mask/` |
| `llm_response` | string | Yes | The LLM's reply text containing placeholder tokens |

**Response (200)**

```json
{
  "unmasked_response": "Hello Alice Smith! I can see your email is alice@example.com."
}
```

The LLM response (with placeholders) and the unmasked response are both persisted to the session record for audit purposes.

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Invalid UUID format or missing field |
| 401 | Not authenticated |
| 404 | Session not found or belongs to another user |
| 410 | Session has expired (TTL elapsed) |

**curl example**

```bash
curl -s -X POST http://localhost:8000/api/unmask/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "llm_response": "Hello [PERSON_1]! I can see your email is [EMAIL_ADDRESS_1]."
  }'
```

---

### POST /api/mask/structured/

Mask PII in specific fields of a JSON object. Only the fields listed in `mask_fields` are processed; all other fields pass through unchanged. Supports dot-notation for nested fields.

**Auth required:** JWT or API Key

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `data` | object | Yes | The JSON object to process (must not be empty) |
| `mask_fields` | array of strings | Yes | Dot-path field names to mask (e.g. `"user.email"`) |
| `mode` | string | Yes | `"pipeline"` or `"webchat"` |

**Response (200)**

```json
{
  "session_id": "c3d4e5f6-1234-5678-abcd-000000000001",
  "masked_data": {
    "user": {
      "name": "[PERSON_1]",
      "email": "[EMAIL_ADDRESS_1]",
      "department": "Engineering"
    }
  }
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Empty `data`, empty `mask_fields`, invalid `mode`, or missing required field |
| 401 | Not authenticated |

**curl example**

```bash
curl -s -X POST http://localhost:8000/api/mask/structured/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "user": {
        "name": "Alice Smith",
        "email": "alice@example.com",
        "department": "Engineering"
      }
    },
    "mask_fields": ["user.name", "user.email"],
    "mode": "pipeline"
  }'
```

---

### POST /api/unmask/structured/

Restore PII placeholders in a (potentially LLM-modified) JSON object, using the mapping stored in the original session.

**Auth required:** JWT or API Key

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | UUID | Yes | The session ID returned by `/api/mask/structured/` |
| `data` | object | Yes | The JSON object containing placeholder tokens to restore |

**Response (200)**

```json
{
  "data": {
    "user": {
      "name": "Alice Smith",
      "email": "alice@example.com",
      "department": "Engineering"
    }
  }
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Invalid UUID or missing required field |
| 401 | Not authenticated |
| 404 | Session not found or belongs to another user |
| 410 | Session has expired |

**curl example**

```bash
curl -s -X POST http://localhost:8000/api/unmask/structured/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "c3d4e5f6-1234-5678-abcd-000000000001",
    "data": {
      "user": {
        "name": "[PERSON_1]",
        "email": "[EMAIL_ADDRESS_1]",
        "department": "Engineering"
      }
    }
  }'
```

---

## 9. Session Endpoints

Sessions record the full lifecycle of a masking operation: the encrypted original text, masked text, placeholder mapping, and (after unmasking) the LLM response and restored text. Sessions expire after 24 hours by default (`MASK_SESSION_TTL_HOURS`).

### GET /api/sessions/

List all non-expired sessions belonging to the authenticated user, ordered by creation date (newest first).

**Auth required:** JWT or API Key

**Request body:** None

**Response (200)** — array of session objects

```json
[
  {
    "id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "mode": "pipeline",
    "masked_text": "My name is [PERSON_1] and my email is [EMAIL_ADDRESS_1].",
    "llm_provider": "openai",
    "llm_response": "Hello [PERSON_1]! ...",
    "unmasked_response": "Hello Alice Smith! ...",
    "created_at": "2025-04-15T10:00:00Z",
    "expires_at": "2025-04-16T10:00:00Z"
  }
]
```

> **Note:** The `original_text_encrypted` field is not exposed via the API. The raw original text is never returned in list or detail responses.

**curl example**

```bash
curl -s http://localhost:8000/api/sessions/ \
  -H "Authorization: Bearer $TOKEN"
```

---

### GET /api/sessions/{id}/

Retrieve a single session by ID.

**Auth required:** JWT or API Key

**Path parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | UUID | The session's UUID |

**Response (200)** — same schema as list items above

**Error responses**

| Code | Condition |
|------|-----------|
| 404 | Session not found or belongs to another user |

**curl example**

```bash
curl -s http://localhost:8000/api/sessions/f47ac10b-58cc-4372-a567-0e02b2c3d479/ \
  -H "Authorization: Bearer $TOKEN"
```

---

## 10. LLM Provider Key Endpoints

Provider keys store your LLM provider API credentials (OpenAI, Anthropic, Gemini) in Fernet-encrypted form. The encrypted value is stored in the database and the raw key is never returned by the API after creation. Each user can hold at most one active key per provider (enforced by a unique constraint on `(user, provider)`).

### GET /api/provider-keys/

List all provider keys registered by the authenticated user.

**Auth required:** JWT or API Key

**Request body:** None

**Response (200)** — array of provider key metadata (raw key value never returned)

```json
[
  {
    "id": "d1e2f3a4-b5c6-7890-def0-123456789abc",
    "provider": "openai",
    "is_active": true,
    "created_at": "2025-03-10T08:00:00Z"
  }
]
```

**curl example**

```bash
curl -s http://localhost:8000/api/provider-keys/ \
  -H "Authorization: Bearer $TOKEN"
```

---

### POST /api/provider-keys/

Register a provider API key. The key is Fernet-encrypted before being stored; only the metadata is returned.

**Auth required:** JWT or API Key

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `provider` | string | Yes | One of `"openai"`, `"anthropic"`, `"gemini"` |
| `api_key` | string | Yes | Your raw API key for the provider (write-only; never returned) |

**Response (201)**

```json
{
  "id": "d1e2f3a4-b5c6-7890-def0-123456789abc",
  "provider": "openai",
  "is_active": true,
  "created_at": "2025-04-15T12:00:00Z"
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Invalid provider name, or a key for that provider already exists for this user |
| 401 | Not authenticated |

**curl example**

```bash
curl -s -X POST http://localhost:8000/api/provider-keys/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "api_key": "sk-proj-..."
  }'
```

---

### DELETE /api/provider-keys/{id}/

Remove a provider key. This does not revoke the key with the upstream provider.

**Auth required:** JWT or API Key

**Path parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | UUID | The provider key's UUID |

**Response:** 204 No Content

**Error responses**

| Code | Condition |
|------|-----------|
| 404 | Key not found or belongs to another user |

**curl example**

```bash
curl -s -X DELETE http://localhost:8000/api/provider-keys/d1e2f3a4-b5c6-7890-def0-123456789abc/ \
  -H "Authorization: Bearer $TOKEN"
```

---

## 11. Pipeline Endpoint

The pipeline endpoint performs the full mask → call LLM → unmask cycle in a single request. A session record is created and returned, allowing the caller to inspect the intermediate masked text if needed.

### POST /api/pipeline/

Mask PII in the input text, send the masked text to the specified LLM provider, unmask the response, and return all three outputs together.

**Auth required:** JWT or API Key

The user must have an active provider key registered for the requested provider (see [Section 10](#10-llm-provider-key-endpoints)).

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | Yes | The input text to mask and send to the LLM |
| `provider` | string | Yes | One of `"openai"`, `"anthropic"`, `"gemini"` |
| `model` | string | Yes | The model identifier, e.g. `"gpt-4o"`, `"claude-3-5-sonnet-20241022"`, `"gemini-2.0-flash"` |

**Response (200)**

```json
{
  "session_id": "b2c3d4e5-f6a7-8901-bcde-f01234567890",
  "masked_text": "My name is [PERSON_1] and my email is [EMAIL_ADDRESS_1].",
  "llm_response": "Hello [PERSON_1]! I see your email is [EMAIL_ADDRESS_1].",
  "unmasked_response": "Hello Alice Smith! I see your email is alice@example.com."
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Missing fields, invalid provider, or no active provider key for this user |
| 401 | Not authenticated |
| 429 | Per-user rate limit exceeded (see [Section 4](#4-rate-limiting)) |
| 502 | The LLM provider returned an error (upstream failure) |

**Rate limit:** 60 requests per minute per user, shared with the webhook endpoint (see [Section 4](#4-rate-limiting)).

**curl example**

```bash
curl -s -X POST http://localhost:8000/api/pipeline/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "My name is Alice Smith and my email is alice@example.com. Summarize this in one sentence.",
    "provider": "openai",
    "model": "gpt-4o"
  }'
```

---

## 12. Webhook Endpoint

The webhook endpoint is a stateless, single-call alternative to the pipeline. It is designed for automation tools such as n8n. Unlike the pipeline, no session record is stored. Supports both plain text and structured JSON input.

### POST /api/webhook/mask-and-forward/

Mask input, forward to LLM, and return the result. No session is persisted.

**Auth required:** JWT or API Key

**Rate limit:** 60 requests per minute per user

**Request body — plain text mode**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | Yes (if not using `data`) | Raw text to mask and send |
| `provider` | string | Yes | One of `"openai"`, `"anthropic"`, `"gemini"` |
| `model` | string | Yes | Model identifier |
| `system_prompt` | string | No | Optional system prompt prepended to the LLM call |
| `unmask_response` | boolean | No | Whether to unmask placeholders in the response (default: `true`) |

**Request body — structured JSON mode**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `data` | object | Yes (if not using `text`) | JSON object to process |
| `mask_fields` | array of strings | Yes (when `data` is present) | Dot-path fields to mask |
| `provider` | string | Yes | One of `"openai"`, `"anthropic"`, `"gemini"` |
| `model` | string | Yes | Model identifier |
| `system_prompt` | string | No | Optional system prompt |
| `unmask_response` | boolean | No | Default: `true` |

> **Note:** `text` and `data` are mutually exclusive. Providing both returns a 400. When using `data`, `mask_fields` is required.

**Response (200)**

```json
{
  "masked_input": "My name is [PERSON_1] and my email is [EMAIL_ADDRESS_1].",
  "llm_response": "Hello [PERSON_1]! ...",
  "final_response": "Hello Alice Smith! ..."
}
```

When `unmask_response` is `false`, `final_response` equals `llm_response` (placeholders are not restored).

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Missing fields, conflicting fields (`text` + `data`), or no active provider key |
| 401 | Not authenticated |
| 429 | Rate limit exceeded |
| 502 | Upstream LLM provider error |

**curl example — plain text**

```bash
curl -s -X POST http://localhost:8000/api/webhook/mask-and-forward/ \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Summarize this ticket filed by Alice Smith at alice@example.com.",
    "provider": "anthropic",
    "model": "claude-3-5-sonnet-20241022",
    "system_prompt": "You are a helpful support assistant.",
    "unmask_response": true
  }'
```

**curl example — structured JSON**

```bash
curl -s -X POST http://localhost:8000/api/webhook/mask-and-forward/ \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "data": {"reporter": "Alice Smith", "email": "alice@example.com", "issue": "Login broken"},
    "mask_fields": ["reporter", "email"],
    "provider": "openai",
    "model": "gpt-4o"
  }'
```

---

## 13. OpenAI-Compatible Proxy

The proxy endpoint accepts requests in the standard OpenAI `/v1/chat/completions` format. Any client that can target an OpenAI-compatible API can point at this endpoint instead, gaining automatic PII masking with no code changes.

PII is masked in all `user` and `system` role messages before being forwarded. `assistant` messages pass through unchanged. The provider is determined by the model name prefix; no provider field is required in the request.

**Provider routing table**

| Model prefix | Provider |
|---|---|
| `gpt-*` | OpenAI |
| `o1-*` | OpenAI |
| `o3-*` | OpenAI |
| `o4-*` | OpenAI |
| `claude-*` | Anthropic |
| `gemini-*` | Gemini |

The user must have an active provider key registered for the resolved provider.

### POST /api/v1/chat/completions

**Auth required:** JWT or API Key

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `model` | string | Yes | Model identifier (prefix determines provider routing) |
| `messages` | array | Yes | Array of message objects with `role` and `content`; at least one message required |
| `messages[].role` | string | Yes | One of `"system"`, `"user"`, `"assistant"` |
| `messages[].content` | string | Yes | Message text (may be blank) |
| `stream` | boolean | No | Return a Server-Sent Events stream instead of a complete JSON response (default: `false`) |
| `temperature` | float | No | Passed through for compatibility; not currently forwarded to providers |
| `max_tokens` | integer | No | Passed through for compatibility; not currently forwarded to providers |

> **Note:** `temperature` and `max_tokens` are accepted without error for drop-in compatibility but are not currently forwarded to the underlying provider. The Anthropic provider is called with a fixed `max_tokens` of 4096.

**Response (200) — non-streaming**

```json
{
  "id": "chatcmpl-550e8400e29b41d4a716446655440000",
  "object": "chat.completion",
  "created": 1744723200,
  "model": "gpt-4o",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Hello Alice Smith! How can I help you today?"
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 0,
    "completion_tokens": 0,
    "total_tokens": 0
  }
}
```

> **Note:** Token usage counts are stub values (always 0). Real token counting is not implemented.

**Response (200) — streaming (`stream: true`)**

Returns `Content-Type: text/event-stream`. The response is chunked into 20-character SSE frames followed by a `[DONE]` sentinel:

```
data: {"id":"chatcmpl-...","object":"chat.completion.chunk","created":1744723200,"model":"gpt-4o","choices":[{"index":0,"delta":{"content":"Hello Alice"},"finish_reason":null}]}

data: {"id":"chatcmpl-...","object":"chat.completion.chunk","created":1744723200,"model":"gpt-4o","choices":[{"index":0,"delta":{},"finish_reason":"stop"}]}

data: [DONE]
```

> **Note:** Streaming is simulated. The service calls the provider synchronously and receives a full response string, which it then chunks into 20-character SSE frames. This means the first chunk does not arrive until the provider has finished generating the full response.

**Error responses** (OpenAI envelope format)

| Code | Condition |
|------|-----------|
| 400 | Unknown model prefix, missing messages, or no active provider key |
| 401 | Not authenticated |
| 502 | Upstream LLM provider error |

**curl example — non-streaming**

```bash
curl -s -X POST http://localhost:8000/api/v1/chat/completions \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "My name is Alice Smith. What is 2 + 2?"}
    ]
  }'
```

**curl example — streaming**

```bash
curl -s -X POST http://localhost:8000/api/v1/chat/completions \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  --no-buffer \
  -d '{
    "model": "claude-3-5-sonnet-20241022",
    "messages": [
      {"role": "user", "content": "Summarize the risks of storing PII in LLM prompts."}
    ],
    "stream": true
  }'
```

---

## 14. Pattern Endpoints

Custom patterns extend the built-in Presidio entity detection with user-defined regex or keyword rules. Patterns have a scope:

- **`user`** — visible and applied only for the creating user.
- **`global`** — visible and applied for all users; only superusers may create or modify global patterns.

Both global and user-scoped patterns are returned by `GET /api/patterns/` for the authenticated user. The masking engine applies both during masking.

### GET /api/patterns/packs/

List all available pre-built pattern packs with per-pack metadata and the full list of pattern definitions in each pack.

**Auth required:** JWT or API Key

**Request body:** None

**Response (200)**

```json
{
  "packs": [
    {
      "id": "wazuh-siem",
      "name": "Wazuh/SIEM PII Pack",
      "description": "Pre-built regex patterns for masking common PII found in SIEM and Wazuh log data.",
      "pattern_count": 9,
      "loaded_count": 0,
      "enabled_count": 0,
      "patterns": [
        {
          "name": "Internal Hostname",
          "pattern_type": "regex",
          "placeholder_label": "HOSTNAME",
          "description": "Matches internal corporate hostnames with common TLDs"
        }
      ]
    }
  ]
}
```

**curl example**

```bash
curl -s http://localhost:8000/api/patterns/packs/ \
  -H "Authorization: Bearer $TOKEN"
```

---

### POST /api/patterns/packs/{pack_id}/{action}/

Enable or disable all patterns in a pack. Admin (`is_staff`) required.

**Auth required:** JWT or API Key + `is_staff`

**Path parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `pack_id` | string | The pack's ID (e.g. `"wazuh-siem"`) |
| `action` | string | `"enable"` or `"disable"` |

**Request body:** None

**Response (200)**

```json
{
  "pack_id": "wazuh-siem",
  "action": "enable",
  "patterns_updated": 9
}
```

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | `action` is not `"enable"` or `"disable"` |
| 401 | Not authenticated |
| 403 | Not staff |
| 404 | `pack_id` not found |

**curl example**

```bash
curl -s -X POST http://localhost:8000/api/patterns/packs/wazuh-siem/enable/ \
  -H "Authorization: Bearer $TOKEN"
```

---

### GET /api/patterns/

List all patterns visible to the authenticated user: their own user-scoped patterns and all global patterns.

**Auth required:** JWT or API Key

**Request body:** None

**Response (200)** — array of pattern objects

```json
[
  {
    "id": "e5f6a7b8-c9d0-1234-5678-abcdef012345",
    "name": "Employee ID",
    "pattern_type": "regex",
    "pattern_value": "EMP-\\d{6}",
    "placeholder_label": "EMPLOYEE_ID",
    "scope": "user",
    "is_active": true,
    "is_editable": true,
    "created_at": "2025-04-01T09:00:00Z"
  }
]
```

The `is_editable` field reflects whether the requesting user may modify this pattern (true for superusers on any pattern; true for regular users on their own `user`-scoped patterns).

**curl example**

```bash
curl -s http://localhost:8000/api/patterns/ \
  -H "Authorization: Bearer $TOKEN"
```

---

### POST /api/patterns/

Create a new custom pattern.

**Auth required:** JWT or API Key

**Request body**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Human-readable name for the pattern |
| `pattern_type` | string | Yes | `"regex"` or `"keyword"` |
| `pattern_value` | string | Yes | For `regex`: a valid Python regex string. For `keyword`: comma-separated keyword list |
| `placeholder_label` | string | Yes | The entity type used in placeholders, e.g. `"EMPLOYEE_ID"` (max 50 chars) |
| `scope` | string | No | `"user"` (default) or `"global"` (superadmin only) |
| `is_active` | boolean | No | Whether to apply this pattern during masking (default: `true`) |

> **Note:** Regex patterns are validated at creation time. An invalid regex returns a 400 with a descriptive error in the `pattern_value` field.

**Response (201)** — the created pattern object (same schema as list)

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Invalid regex, missing required field, or non-superuser attempting `"global"` scope |
| 401 | Not authenticated |

**curl example**

```bash
curl -s -X POST http://localhost:8000/api/patterns/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Employee ID",
    "pattern_type": "regex",
    "pattern_value": "EMP-\\d{6}",
    "placeholder_label": "EMPLOYEE_ID",
    "scope": "user",
    "is_active": true
  }'
```

---

### GET /api/patterns/{id}/

Retrieve a single pattern by ID.

**Auth required:** JWT or API Key

**Path parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | UUID | The pattern's UUID |

**Response (200)** — single pattern object

**Error responses**

| Code | Condition |
|------|-----------|
| 404 | Pattern not found or not visible to this user |

**curl example**

```bash
curl -s http://localhost:8000/api/patterns/e5f6a7b8-c9d0-1234-5678-abcdef012345/ \
  -H "Authorization: Bearer $TOKEN"
```

---

### PUT /api/patterns/{id}/

Fully replace a pattern. The caller must be the pattern's owner (for `user`-scoped patterns) or a superuser (for any pattern).

**Auth required:** JWT or API Key + ownership or superadmin

**Path parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | UUID | The pattern's UUID |

**Request body:** Same required fields as `POST /api/patterns/`

**Response (200)** — the updated pattern object

**Error responses**

| Code | Condition |
|------|-----------|
| 400 | Validation error |
| 401 | Not authenticated |
| 403 | Not the owner or not a superuser |
| 404 | Pattern not found |

**curl example**

```bash
curl -s -X PUT http://localhost:8000/api/patterns/e5f6a7b8-c9d0-1234-5678-abcdef012345/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Employee ID",
    "pattern_type": "regex",
    "pattern_value": "EMP-\\d{7}",
    "placeholder_label": "EMPLOYEE_ID",
    "scope": "user"
  }'
```

---

### PATCH /api/patterns/{id}/

Partially update a pattern. Only the supplied fields are changed.

**Auth required:** JWT or API Key + ownership or superadmin

**Path parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | UUID | The pattern's UUID |

**Request body:** Any subset of the `POST /api/patterns/` fields

**Response (200)** — the updated pattern object

**curl example**

```bash
curl -s -X PATCH http://localhost:8000/api/patterns/e5f6a7b8-c9d0-1234-5678-abcdef012345/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_active": false}'
```

---

### DELETE /api/patterns/{id}/

Delete a pattern. The caller must be the pattern's owner or a superuser.

**Auth required:** JWT or API Key + ownership or superadmin

**Path parameters**

| Parameter | Type | Description |
|-----------|------|-------------|
| `id` | UUID | The pattern's UUID |

**Response:** 204 No Content

**Error responses**

| Code | Condition |
|------|-----------|
| 401 | Not authenticated |
| 403 | Not the owner or not a superuser |
| 404 | Pattern not found |

**curl example**

```bash
curl -s -X DELETE http://localhost:8000/api/patterns/e5f6a7b8-c9d0-1234-5678-abcdef012345/ \
  -H "Authorization: Bearer $TOKEN"
```

---

## 15. PII Masking Reference

### 15.1 Detection Engine

The service uses [Microsoft Presidio](https://microsoft.github.io/presidio/) with a spaCy NLP backend (`en_core_web_lg` or equivalent). Detection runs in English (`language="en"`).

### 15.2 Built-in Entity Types

Presidio detects the following entity types out of the box. The list below covers those most commonly encountered; the full set depends on the installed Presidio version and spaCy model.

| Entity Type | Example |
|---|---|
| `PERSON` | Alice Smith |
| `EMAIL_ADDRESS` | alice@example.com |
| `PHONE_NUMBER` | +1-202-555-0100 |
| `CREDIT_CARD` | 4111 1111 1111 1111 |
| `IBAN_CODE` | GB29 NWBK 6016 1331 9268 19 |
| `URL` | https://internal.corp |
| `IP_ADDRESS` | 192.0.2.1 |
| `LOCATION` | San Francisco |
| `DATE_TIME` | January 15, 2025 |
| `NRP` | (Nationality, Religion, Political group references) |
| `MEDICAL_LICENSE` | MD12345 |
| `US_SSN` | 123-45-6789 |
| `US_PASSPORT` | A12345678 |
| `US_DRIVER_LICENSE` | D12345678 |

### 15.3 Placeholder Format

Each detected entity is replaced with a placeholder of the form:

```
[ENTITY_TYPE_N]
```

where `N` is a 1-based counter that increments for each occurrence of that entity type within the same text. Counters are independent per entity type. Overlapping spans are resolved by preferring higher confidence scores, then longer spans.

**Example:**

```
Input:   "Alice Smith called Bob Jones. Alice's email is alice@corp.com."
Output:  "[PERSON_1] called [PERSON_2]. [PERSON_1]'s email is [EMAIL_ADDRESS_1]."
Mapping: {
  "[PERSON_1]": "Alice Smith",
  "[PERSON_2]": "Bob Jones",
  "[EMAIL_ADDRESS_1]": "alice@corp.com"
}
```

Note that repeated occurrences of the same entity value each get a unique placeholder position (they are not de-duplicated). The `[PERSON_1]` placeholder above corresponds to the first occurrence of `"Alice Smith"` — when the text is later unmasked, all occurrences of `[PERSON_1]` are replaced with `"Alice Smith"`.

### 15.4 Custom Patterns

Custom patterns augment Presidio's built-in recognition. They are loaded from the database at request time and added to the analyzer engine before each masking call. There are two pattern types:

**Regex patterns**

Define a Python-compatible regular expression. The pattern fires when the regex matches. The match is tagged with the `placeholder_label` you specify.

```json
{
  "name": "Employee ID",
  "pattern_type": "regex",
  "pattern_value": "EMP-\\d{6}",
  "placeholder_label": "EMPLOYEE_ID"
}
```

**Keyword patterns**

Define a comma-separated list of exact-match keywords. Any occurrence of these words in the input is replaced.

```json
{
  "name": "Project Codenames",
  "pattern_type": "keyword",
  "pattern_value": "Project Falcon, Operation Delta, Codename Aurora",
  "placeholder_label": "PROJECT_NAME"
}
```

### 15.5 Session Lifecycle

- Sessions are created by `POST /api/mask/`, `POST /api/mask/structured/`, `POST /api/pipeline/`, and `POST /api/v1/chat/completions` (the proxy creates a session implicitly).
- The `POST /api/webhook/mask-and-forward/` endpoint is stateless and does **not** create a session.
- Sessions expire after `MASK_SESSION_TTL_HOURS` hours (default: 24). Expired sessions are excluded from `GET /api/sessions/`.
- Attempting to unmask against an expired session returns HTTP 410 Gone.
- The original plaintext is Fernet-encrypted at rest and is never returned by the API.

---

## 16. Workflow Examples

### 16.1 Basic: Login → Mask → Call LLM Manually → Unmask

This workflow gives you full control at each step. You manage the LLM call yourself with your own API key.

```bash
# Step 1: Obtain a JWT token
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "secret"}' \
  | jq -r '.access')

echo "Token acquired."

# Step 2: Mask the text
MASK_RESPONSE=$(curl -s -X POST http://localhost:8000/api/mask/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "My name is Alice Smith and my phone is 555-867-5309. Please summarize my issue.",
    "mode": "webchat"
  }')

SESSION_ID=$(echo $MASK_RESPONSE | jq -r '.session_id')
MASKED_TEXT=$(echo $MASK_RESPONSE | jq -r '.masked_text')

echo "Session ID: $SESSION_ID"
echo "Masked text: $MASKED_TEXT"

# Step 3: Send masked text to the LLM directly (your own OpenAI key, no PII sent)
LLM_RESPONSE=$(curl -s -X POST https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"model\": \"gpt-4o\",
    \"messages\": [{\"role\": \"user\", \"content\": \"$MASKED_TEXT\"}]
  }" | jq -r '.choices[0].message.content')

echo "LLM responded: $LLM_RESPONSE"

# Step 4: Unmask the LLM's response
UNMASKED=$(curl -s -X POST http://localhost:8000/api/unmask/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"session_id\": \"$SESSION_ID\",
    \"llm_response\": $(echo $LLM_RESPONSE | jq -Rs .)
  }" | jq -r '.unmasked_response')

echo "Final response: $UNMASKED"
```

---

### 16.2 Pipeline: Login → Pipeline (Single Call)

Use this when you have a provider key stored in the service and want a single-call interface.

```bash
# Step 1: Obtain token
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "secret"}' \
  | jq -r '.access')

# Step 2 (optional): Register your OpenAI key if not already done
curl -s -X POST http://localhost:8000/api/provider-keys/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "openai",
    "api_key": "sk-proj-..."
  }'

# Step 3: Run the full pipeline in one call
curl -s -X POST http://localhost:8000/api/pipeline/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Draft a reply to an email from Bob Jones at bob@widgets.com who is asking about invoice #INV-4421.",
    "provider": "openai",
    "model": "gpt-4o"
  }' | jq '{session_id, unmasked_response}'
```

The response includes `session_id`, `masked_text`, `llm_response`, and `unmasked_response`. The session is stored and can be retrieved later via `GET /api/sessions/{session_id}/`.

---

### 16.3 Webhook: API Key + Stateless Webhook Endpoint

Use this for n8n, Zapier, or any automation tool that needs a single HTTP call with no session management. The API key eliminates the need for token refresh logic.

```bash
# Step 1: Create an API key (one-time, using JWT)
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "secret"}' \
  | jq -r '.access')

API_KEY=$(curl -s -X POST http://localhost:8000/api/keys/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"label": "n8n webhook"}' \
  | jq -r '.raw_key')

echo "API Key (save this): $API_KEY"

# Step 2: Call the webhook endpoint directly with the API key (no JWT needed)
curl -s -X POST http://localhost:8000/api/webhook/mask-and-forward/ \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "Alert: user alice@corp.com from 10.0.1.55 triggered rule 550 on host WEB-SERVER-01.corp.",
    "provider": "anthropic",
    "model": "claude-3-5-sonnet-20241022",
    "system_prompt": "You are a security analyst. Analyze this SIEM alert concisely.",
    "unmask_response": true
  }' | jq '{masked_input, final_response}'
```

---

### 16.4 OpenAI Proxy: Drop-In Replacement

Point any OpenAI SDK client at the proxy endpoint. PII masking is applied automatically with no changes to your application code beyond the base URL and auth header.

```bash
# Using curl as a drop-in replacement for the OpenAI API
curl -s -X POST http://localhost:8000/api/v1/chat/completions \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "messages": [
      {
        "role": "system",
        "content": "You are a helpful assistant that summarizes support tickets."
      },
      {
        "role": "user",
        "content": "Ticket from John Doe (john.doe@acme.com, SSN 123-45-6789): Cannot log in to portal since password reset."
      }
    ]
  }' | jq '.choices[0].message.content'
```

**Using the OpenAI Python SDK against the proxy**

```python
import openai

client = openai.OpenAI(
    base_url="http://localhost:8000/api/v1/",
    api_key="pii_your_api_key_here",  # the X-API-Key value, passed as the api_key parameter
)

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[
        {"role": "user", "content": "Summarize this: John Doe at john@example.com called about order #12345."}
    ],
)

print(response.choices[0].message.content)
```

> **Note:** The OpenAI SDK sends the `api_key` value as an `Authorization: Bearer` header, not as `X-API-Key`. The proxy endpoint accepts both auth methods, so this works transparently. If you pass a JWT access token as the `api_key` in the SDK, it is likewise accepted.

**Streaming with curl**

```bash
curl -s -X POST http://localhost:8000/api/v1/chat/completions \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  --no-buffer \
  -d '{
    "model": "gemini-2.0-flash",
    "messages": [
      {"role": "user", "content": "Write a short poem about privacy."}
    ],
    "stream": true
  }'
```
