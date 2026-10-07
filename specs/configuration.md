# Configuration

## Required setup

- Keep runtime secrets in `backend/.env` or a deployment secret source and browser configuration in `frontend/.env`. Copy the corresponding `.env.example` files for local development. Neither `.env` file belongs in version control.
- `LITELLM_API_KEY` is a required settings field; supply a working value to use the default LiteLLM provider. Gemini, OpenAI, Anthropic, and Ollama are selected per request. Provider-specific values supplied in the UI must stay separate by provider.
- `MODEL_BASE_URL_ALLOWLIST` is a JSON map from provider names to exact additional base URLs, for example `{"ollama":["http://ollama:11434/v1"]}`. An omitted request URL uses the provider default. A caller may select the configured LiteLLM URL or an additional URL explicitly approved for `litellm`; only approve destinations trusted to receive its server key. OpenAI and Anthropic custom URLs must also be listed under their respective providers. Gemini does not accept a base URL.
- In development, `VITE_API_BASE_URL` must be reachable from the browser and `CORS_ORIGINS` must contain the exact frontend origin. The production image builds with an empty API base URL, so a local browser uses same-origin `/api` and `ws://` Live Tail. Production Compose supplies local `127.0.0.1` and `localhost` browser origins based on `PROD_HTTP_PORT`; `deploy.sh` does not need a public URL.
- Set `AWS_REGION` to the region to search. Leave `AWS_PROFILE` empty when using exported credentials or an instance/task role. Set `AWS_ROLE_ARN` only when the backend should assume a monitoring role; set `AWS_ROLE_EXTERNAL_ID` when that role's trust policy requires it.
- `AWS_INCLUDE_LINKED_ACCOUNTS=true` enables linked log-group discovery. `CLOUDTRAIL_LOG_GROUP_IDENTIFIERS` supplies explicit centralized CloudTrail groups; without either setting, CloudTrail uses regional `LookupEvents`.
- Set `MASKING_SERVICE_API_KEY` to enable the external masking service. If it is absent or that service fails, local regex masking still runs. Use a trusted certificate and enable `MASKING_SERVICE_VERIFY_SSL` when the masking endpoint supports it.
- Respect the declared bounds for Live Tail timeout/session count and analysis token/output settings in `backend/app/config.py`; other numeric settings have defaults but no Pydantic range constraint. Treat Live Tail price and free-tier values as UI estimates; actual AWS billing is determined by the AWS account.
- The service has no built-in user authentication. A public deployment must restrict access through its network or an authenticated proxy; CORS and rate limiting do not grant access control.

## Acceptance checks

- Local setup starts both services, loads `/api/health` and `/api/config`, and fetches log groups with the intended AWS identity. A health response alone does not verify AWS permission.
- Changing the API URL or CORS origin allows the browser's HTTP calls and Live Tail WebSocket handshake from the intended frontend origin.
- A configuration change to a container environment is applied by recreating the container. Verify the effective setting after recreation.
- An unapproved model URL is rejected before any provider client or network request is created; an approved exact URL is accepted for its matching provider.
- Production Compose binds only the frontend's host loopback port and leaves the backend on the Docker network. Verify the other app reaches the intended local endpoint; add TLS and caller access control before allowing remote API calls.
