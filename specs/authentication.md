# Authentication and authorization

Production uses one shared `ANOMALOG_API_KEY` for server-to-server callers. The calling app sends it as `X-API-Key` on every HTTP request and on the Live Tail WebSocket handshake. The server compares the supplied value with the configured secret before handling AWS or model work. Production startup requires a key of at least 32 characters. Development can leave the key unset. `GET /api/health` and HTTP `OPTIONS` preflight remain unauthenticated.

Generate the key on the production host with `openssl rand -hex 32`. Store it in that host's ignored `backend/.env` and in the calling app's server-side secret configuration; push only the blank `.env.example` template to Git. For rotation, update both applications' secret configuration and recreate the Anomalog backend. `LITELLM_API_KEY` is a separate provider key and must not be reused as the Anomalog caller key. See [deployment.md](deployment.md) for the full host setup.

| Requested topic | Current state |
| --- | --- |
| Login, registration, password handling | Not implemented; callers use a provisioned machine secret. |
| Session/token lifecycle and refresh | No session or refresh. Rotate by updating the secret in both apps and recreating the backend. |
| App roles and protected resources | One shared access level; routes do not distinguish individual callers. |
| Logout and failed-auth response | No logout. Missing or wrong HTTP key returns 401; a WebSocket handshake closes with code 1008. |
| AWS identity and permissions | Backend boto3 chain and optional STS role assumption; IAM controls AWS operations, not which human uses Anomalog. |
| External masking-service authentication | Backend uses `X-API-Key` for its outbound call if configured; this does not authenticate Anomalog users. |

The React browser UI has no way to supply a WebSocket `X-API-Key`, so it is not a production client of the protected API. Use the server-to-server API from the other app. The separate masking service described in [root masking reference](../api-reference-pii-masking.md) has its own authentication system; its endpoints are **not** implemented by this repository. Network exposure remains a separate concern ([ASM-003](assumptions.md#asm-003)).
