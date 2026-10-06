# Configuration

## Required setup

- Keep runtime secrets in `backend/.env` or a deployment secret source and browser configuration in `frontend/.env`. Copy the corresponding `.env.example` files for local development. Neither `.env` file belongs in version control.
- `LITELLM_API_KEY` is a required settings field; supply a working value to use the default LiteLLM provider. Gemini, OpenAI, Anthropic, and Ollama are selected per request. Provider-specific values supplied in the UI must stay separate by provider.
- `VITE_API_BASE_URL` must be reachable from the user's browser. For HTTPS deployment, use an HTTPS API URL so Live Tail uses `wss://`. `CORS_ORIGINS` must contain the exact frontend origin, including scheme and port when present.
- Set `AWS_REGION` to the region to search. Leave `AWS_PROFILE` empty when using exported credentials or an instance/task role. Set `AWS_ROLE_ARN` only when the backend should assume a monitoring role; set `AWS_ROLE_EXTERNAL_ID` when that role's trust policy requires it.
- `AWS_INCLUDE_LINKED_ACCOUNTS=true` enables linked log-group discovery. `CLOUDTRAIL_LOG_GROUP_IDENTIFIERS` supplies explicit centralized CloudTrail groups; without either setting, CloudTrail uses regional `LookupEvents`.
- Set `MASKING_SERVICE_API_KEY` to enable the external masking service. If it is absent or that service fails, local regex masking still runs. Use a trusted certificate and enable `MASKING_SERVICE_VERIFY_SSL` when the masking endpoint supports it.
- Keep search, analysis, Live Tail, and inbound rate limits within the validated ranges in `backend/app/config.py`. Treat Live Tail price and free-tier values as UI estimates; actual AWS billing is determined by the AWS account.
- The service has no built-in user authentication. A public deployment must restrict access through its network or an authenticated proxy; CORS and rate limiting do not grant access control.

## Acceptance checks

- Local setup starts both services, loads `/api/health` and `/api/config`, and fetches log groups with the intended AWS identity. A health response alone does not verify AWS permission.
- Changing the API URL or CORS origin allows the browser's HTTP calls and Live Tail WebSocket handshake from the intended frontend origin.
- A configuration change to a container environment is applied by recreating the container. Verify the effective setting after recreation.
