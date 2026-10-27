# Deployment

## Verified local development path

1. Create `backend/.venv`, install `backend/requirements.txt`, and copy `backend/.env.example` to `backend/.env`. Supply a real `LITELLM_API_KEY` for the default provider and appropriate AWS credentials/profile/role.
2. Run `npm install` in `frontend/`, copy `frontend/.env.example` to `frontend/.env`, and set `VITE_API_BASE_URL` for the browser-accessible backend.
3. Run `./dev.sh`, or run Uvicorn on port 8000 and `npm run dev` on port 5173 separately. `docker compose up --build` is another checked-in development path. Both Dockerfiles and Compose run development reload servers.
4. Check `GET /api/health`, then `GET /api/config` and an allowed log-group discovery to validate configuration and AWS access. Health alone checks only process response.

Sources: `dev.sh`, both Dockerfiles, `docker-compose.yml`, both `.env.example` files, [root README](../README.md). Backend build uses Python 3.12 slim and `pip install`; frontend build uses Node 20 slim and `npm install`. The frontend production build command is `npm run build`, which runs TypeScript build plus Vite bundle; Compose does not serve that bundle.

## Staging and production

The repository contains `backend/.env.example` with blank secrets; `.gitignore` excludes `backend/.env`. Push the code and example file, then create `backend/.env` separately on each production EC2 host after clone/pull. On a new host, run `cp backend/.env.example backend/.env` and `chmod 600 backend/.env`. Future Git pulls leave this ignored file in place. Never commit production key values or put them in the frontend build.

`./dev.sh` permits an unset Anomalog caller key. `./deploy.sh` selects the production configuration and requires one, even though it binds only to the host's loopback interface.

Generate a machine key with `openssl rand -hex 32` and put it in `ANOMALOG_API_KEY=` in the production host's `backend/.env`. The frontend Nginx proxy injects this key into browser API requests and Live Tail WebSocket handshakes without putting it in JavaScript. Other direct machine callers need the same key in server-side secret configuration. Set `LITELLM_API_KEY` separately when using default model analysis, plus the intended AWS region and instance/assumed role. The Anomalog key is generated locally; it is not an AWS or LiteLLM credential.

For an HTTPS LiteLLM proxy signed by the internal CA, obtain the trusted CA PEM from its operator, put it at `backend/certs/internal-ca.pem`, and set `LITELLM_CA_BUNDLE=/app/certs/internal-ca.pem` with `LITELLM_BASE_URL=https://llm.etapinc.com/v1` in `backend/.env`. Production Compose mounts `backend/certs` read-only into the backend. Recreate the backend container after the change. Confirm the mounted PEM is the CA certificate using its independently verified fingerprint, then run the model connection test; the shallow health check does not test LiteLLM TLS.

`deploy.sh` is the checked-in local production entry point. It requires `backend/.env` with `ANOMALOG_API_KEY`, Docker Compose v2, and curl; no public URL is required. It builds `backend/Dockerfile.prod` and `frontend/Dockerfile.prod` through `docker-compose.prod.yml`, recreates containers, and checks the locally proxied static page and `/api/health`. The frontend image uses `npm ci` and `npm run build`, then Nginx serves the static bundle and proxies `/api/*` including WebSockets. The backend image runs one Uvicorn process without reload. Production requires the shared API key before serving protected routes. `deploy.sh` deploys the current checkout and does not pull Git or rewrite `.env`.

The production frontend binds only `127.0.0.1:${PROD_HTTP_PORT:-8080}` on the host; the backend has no published host port. A same-host process calls `http://127.0.0.1:${PROD_HTTP_PORT:-8080}/api`; a container attached to the `anomalog-prod_default` network calls `http://backend:8000/api`. The browser UI works through the Nginx proxy's injected machine key. Anyone who can reach the frontend can access shared history and the protected API; no individual sign-in exists. Remote hosts need separately configured trusted HTTPS/VPN ingress ([ASM-003](assumptions.md#asm-003)). The development Compose file still publishes 8000/5173 and uses reload servers.

## Environment, migration, and rollback

Required settings and optional provider/AWS/masking limits are in [configuration.md](configuration.md); IAM is in [iam_setup.md](iam_setup.md). Environment changes in Compose require container recreation to take effect. Shared history uses a SQLite file on the `history_data` Docker volume. The table is created on first access; back up the volume before destructive deployments. The browser imports its existing local history once after the API is available.

The production backend has a shallow container health check; `deploy.sh` checks only local UI and API response. It does not validate AWS identity, masking service, model endpoint, or Live Tail. No staging environment, CI/CD, or automatic rollback is checked in. Retain the previous image/commit and configuration for manual rollback; after restoring them, rerun `deploy.sh` and verify the local API, WebSocket upgrade where used, and an allowed AWS read. Do not test billable Live Tail automatically in CI.

## Production acceptance checks

- `bash -n deploy.sh` and `docker compose --env-file backend/.env -f docker-compose.prod.yml config --quiet` pass with no public URL. The resulting configuration publishes only a loopback frontend port and no backend port.
- The built frontend serves `/` and proxies protected `/api/*` and the Live Tail WebSocket route with the machine key. A same-host process can call the loopback API; a container on `anomalog-prod_default` can call the backend service name. Neither endpoint is reachable from another host by default.
- Saving an investigation on one browser makes it visible from another browser with access to the same deployment. The SQLite volume retains it across container recreation.
- Production backend startup fails without `ANOMALOG_API_KEY`. Protected HTTP routes return 401 without the correct header; Live Tail rejects an unauthenticated handshake before starting a stream.
- The production host has its own untracked `backend/.env` with restrictive permissions; the calling app has the same Anomalog key in its server-side secret store. No production key value appears in Git or the browser bundle.
- Confirm the backend uses the intended IAM identity and can read one allowed log group while denying one unauthorized group. Health alone does not verify AWS access.
