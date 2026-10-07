# Security

## Current security model

The FastAPI app requires a shared machine API key when configured, and production refuses startup without one. It has no end-user identity or per-user authorization (`backend/app/main.py`). The backend holds AWS credentials through boto3 and may assume a monitoring role; the browser does not receive AWS credentials. The browser may supply a provider API key and approved model `base_url` in analysis/test request bodies during development. `backend/.env` and `frontend/.env` are ignored by Git; only backend settings should contain server secrets. See [authentication.md](authentication.md), [iam_setup.md](iam_setup.md), and [configuration.md](configuration.md).

| Boundary/asset | Existing control | Limit |
| --- | --- | --- |
| AWS logs and CloudTrail | Machine API key, backend-only boto3 calls, optional assumed role, IAM, masking | Every caller with the shared key can ask backend to read within its IAM permissions. |
| Raw log messages | External masking when configured, local regex fallback, analysis re-mask | Regex coverage is finite; metadata and user-entered prompts are separate surfaces. |
| Provider keys | Server settings or per-request override; `/api/config` only exposes booleans | Request body transits browser/backend and may reach configured provider destination. |
| HTTP API | Shared API key when configured, Pydantic validation, per-IP per-process rate limit, CORS | No per-user identity; some schemas lack size/order bounds. |
| WebSocket | Shared API key when configured, Origin check when header exists, first-message schema, session/inactivity/queue limits | Missing Origin is accepted; no per-user identity check. |
| Local investigation history | Browser `localStorage`, explicit delete, max 20 entries | Full questions/answers persist in the browser profile without age expiry. |
| CSV output | Formula prefix escaping in `LogViewer.tsx` | Exported content can still contain information the masker missed. |

Production Compose keeps the backend on the Compose network and binds the frontend to host loopback. Its intended callers run on the same EC2 host or Docker network, so no public DNS or HTTPS ingress is configured. Local processes and containers on that network still need the machine key; any future remote ingress requires TLS. There is no application-level encryption-at-rest setting because no app database exists; browser local storage is controlled by the browser/host. SDK/HTTP traffic uses each client configuration; the external masking client currently defaults to `MASKING_SERVICE_VERIFY_SSL=false` in `backend/app/config.py`.

Pydantic and route/service checks validate some input shapes, counts, and ranges; they do not supply a global request-body limit. React renders log text as text nodes, while CSV export adds a formula prefix guard. Backend error strings and provider diagnostics need review before being treated as safe to expose. Python dependencies in `backend/requirements.txt` mostly use lower bounds rather than exact locks; frontend has `package-lock.json`. No dependency vulnerability scan is checked in. These are observations about the current controls, not proof that a particular payload is exploitable.

## Observed risks (not claims of confirmed exploitation)

1. **Shared machine identity and local trust boundary:** development `docker-compose.yml` publishes 8000 and 5173; production Compose binds only the frontend to host loopback and requires one shared key. Any process holding that key can read allowed AWS data, call models, and start billable Live Tail sessions. Protect distribution of the key and confirm no separate ingress exposes it over cleartext HTTP.
2. **Masking transport verification disabled by default:** `backend/app/config.py` and `core/masking_http_client.py` allow unverified TLS for raw-log masking traffic. A network attacker on that path could undermine confidentiality; no exploit has been demonstrated.
3. **Model destination configuration:** analysis/test requests may include `base_url`, but the backend accepts only an exact provider default or a URL in that provider's `MODEL_BASE_URL_ALLOWLIST`. An operator who approves an untrusted LiteLLM URL may expose its server key and submitted data. The allowlist controls application-selected endpoints; it is not an egress firewall or DNS-pinning control.
4. **Unsigned search cursor:** `group_pagination.py` validates structure and query hash but does not authenticate compressed cursor contents. A caller able to construct a cursor could potentially alter pending events or group state. The exact exploitability and IAM impact need a dedicated test/review.
5. **Public development diagnostic:** `/api/mask/test` is registered in all environments with no route-specific payload cap. It can consume resources and reveals masking behavior to any API caller.
6. **Local history sensitivity:** `LogSummary.tsx` saves generated answers and questions to browser storage. Local users, browser extensions, or same-origin scripts may access it; no age-based expiry exists.
7. **Unbounded fields in several request models:** `CloudWatchSearchRequest.log_group_names`, analysis event message content, prompt/history text, and mask-test lines lack Pydantic length caps. Service count/token limits mitigate some paths, but request parsing itself is not globally bounded in app code.
8. **Default LiteLLM transport:** `backend/app/config.py` defaults `LITELLM_BASE_URL` to an `http://` internal proxy URL. Whether this hop is protected by private networking is not verifiable here; model evidence and the proxy key could be exposed if the path is untrusted.
9. **Masking scope:** `AnomalyService.analyze` re-masks `event.message`; it does not apply the same masker to user-supplied question, conversation history, source description, or other event metadata before constructing provider input. Treat those as potentially sensitive.

No secret values are reproduced in this specification. These are code-observed risks; validate reachability, threat model, and mitigations before labeling any as a confirmed vulnerability. No compliance standard or dependency scanning pipeline is configured in this checkout.

## Intended safeguards and validation

REQ-SEC-001 through REQ-SEC-007 in [requirements.md](requirements.md) capture privacy and deployment obligations. For changes touching masking, credentials, CORS, IAM, URL overrides, local history, or cursors, add focused regression tests and review logs/errors for sensitive output. **Recommendations** for closing observed gaps are in [roadmap.md](roadmap.md), not current-behavior claims.
