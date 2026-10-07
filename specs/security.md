# Security

## Current security model

The FastAPI app has **no built-in end-user authentication or authorization** (`backend/app/main.py`). Reachability of the HTTP and WebSocket ports is therefore the practical access boundary. The backend holds AWS credentials through boto3 and may assume a monitoring role; the browser does not receive AWS credentials. The browser may supply a provider API key and model `base_url` in analysis/test request bodies. `backend/.env` and `frontend/.env` are ignored by Git; only backend settings should contain secrets. See [authentication.md](authentication.md), [iam_setup.md](iam_setup.md), and [configuration.md](configuration.md).

| Boundary/asset | Existing control | Limit |
| --- | --- | --- |
| AWS logs and CloudTrail | Backend-only boto3 calls, optional assumed role, IAM, masking | Anyone with API reachability can ask backend to read within its IAM permissions. |
| Raw log messages | External masking when configured, local regex fallback, analysis re-mask | Regex coverage is finite; metadata and user-entered prompts are separate surfaces. |
| Provider keys | Server settings or per-request override; `/api/config` only exposes booleans | Request body transits browser/backend and may reach configured provider destination. |
| HTTP API | Pydantic validation, per-IP per-process rate limit, CORS | CORS is browser policy, not authentication; some schemas lack size/order bounds. |
| WebSocket | Origin check when header exists, first-message schema, session/inactivity/queue limits | Missing Origin is accepted; no user identity check. |
| Local investigation history | Browser `localStorage`, explicit delete, max 20 entries | Full questions/answers persist in the browser profile without age expiry. |
| CSV output | Formula prefix escaping in `LogViewer.tsx` | Exported content can still contain information the masker missed. |

Production Compose keeps the backend on the Compose network and binds the frontend to host loopback. Its intended callers run on the same EC2 host or Docker network, so no public DNS or HTTPS ingress is configured. Local processes and containers on that network can access the unauthenticated API; any future remote ingress requires its own TLS and access control. There is no application-level encryption-at-rest setting because no app database exists; browser local storage is controlled by the browser/host. SDK/HTTP traffic uses each client configuration; the external masking client currently defaults to `MASKING_SERVICE_VERIFY_SSL=false` in `backend/app/config.py`.

Pydantic and route/service checks validate some input shapes, counts, and ranges; they do not supply a global request-body limit. React renders log text as text nodes, while CSV export adds a formula prefix guard. Backend error strings and provider diagnostics need review before being treated as safe to expose. Python dependencies in `backend/requirements.txt` mostly use lower bounds rather than exact locks; frontend has `package-lock.json`. No dependency vulnerability scan is checked in. These are observations about the current controls, not proof that a particular payload is exploitable.

## Observed risks (not claims of confirmed exploitation)

1. **No app login and local trust boundary:** development `docker-compose.yml` publishes 8000 and 5173; production Compose binds only the frontend to host loopback. Routes have no auth dependency. Any process on the host or container attached to the production network can read allowed AWS data, call models, and start billable Live Tail sessions. Confirm that those callers are trusted and that no separate ingress exposes the service.
2. **Masking transport verification disabled by default:** `backend/app/config.py` and `core/masking_http_client.py` allow unverified TLS for raw-log masking traffic. A network attacker on that path could undermine confidentiality; no exploit has been demonstrated.
3. **Caller-controlled model destination:** `base_url` is accepted in analysis/test requests and passed to provider clients. Without an external access boundary or URL allowlist, this creates a server-side request target and possible network probing/exfiltration surface. This is an architectural risk, not a verified SSRF exploit.
4. **Unsigned search cursor:** `group_pagination.py` validates structure and query hash but does not authenticate compressed cursor contents. A caller able to construct a cursor could potentially alter pending events or group state. The exact exploitability and IAM impact need a dedicated test/review.
5. **Public development diagnostic:** `/api/mask/test` is registered in all environments with no route-specific payload cap. It can consume resources and reveals masking behavior to any API caller.
6. **Local history sensitivity:** `LogSummary.tsx` saves generated answers and questions to browser storage. Local users, browser extensions, or same-origin scripts may access it; no age-based expiry exists.
7. **Unbounded fields in several request models:** `CloudWatchSearchRequest.log_group_names`, analysis event message content, prompt/history text, and mask-test lines lack Pydantic length caps. Service count/token limits mitigate some paths, but request parsing itself is not globally bounded in app code.
8. **Default LiteLLM transport:** `backend/app/config.py` defaults `LITELLM_BASE_URL` to an `http://` internal proxy URL. Whether this hop is protected by private networking is not verifiable here; model evidence and the proxy key could be exposed if the path is untrusted.
9. **Masking scope:** `AnomalyService.analyze` re-masks `event.message`; it does not apply the same masker to user-supplied question, conversation history, source description, or other event metadata before constructing provider input. Treat those as potentially sensitive.

No secret values are reproduced in this specification. These are code-observed risks; validate reachability, threat model, and mitigations before labeling any as a confirmed vulnerability. No compliance standard or dependency scanning pipeline is configured in this checkout.

## Intended safeguards and validation

REQ-SEC-001, REQ-SEC-002, REQ-SEC-003, REQ-SEC-004, and REQ-SEC-005 in [requirements.md](requirements.md) capture privacy and deployment obligations. For changes touching masking, credentials, CORS, IAM, URL overrides, local history, or cursors, add focused regression tests and review logs/errors for sensitive output. **Recommendations** for closing observed gaps are in [roadmap.md](roadmap.md), not current-behavior claims.
