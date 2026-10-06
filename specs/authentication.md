# Authentication and authorization

**Application authentication: Not currently applicable as an implemented feature.** The React app has no login/register/logout screen or token manager; FastAPI routes have no user-auth dependency, session cookie, password store, refresh endpoint, user role, or per-user permission check. `backend/app/main.py` registers CORS and an IP rate limiter only. A request that reaches an API route is not challenged for user identity by Anomalog. See [security.md](security.md).

| Requested topic | Current state |
| --- | --- |
| Login, registration, password handling | Not implemented. |
| Session/token lifecycle and refresh | Not implemented. |
| App roles and protected resources | Not implemented; all registered routes are application-public. |
| Logout and failed-auth response | Not implemented; no app-auth failure code path. |
| AWS identity and permissions | Backend boto3 chain and optional STS role assumption; IAM controls AWS operations, not which human uses Anomalog. |
| External masking-service authentication | Backend uses `X-API-Key` for its outbound call if configured; this does not authenticate Anomalog users. |

The separate masking service described in [root masking reference](../api-reference-pii-masking.md) has its own authentication system; its endpoints are **not** implemented by this repository. The README recommends network restriction or an authenticated reverse proxy for Anomalog, but no proxy configuration is checked in. Whether production actually enforces one is [ASM-003](assumptions.md#asm-003). Adding in-app authentication would require a new product and security decision before defining users, roles, sessions, or logout behavior.
