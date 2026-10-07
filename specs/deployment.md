# Deployment

## Verified local development path

1. Create `backend/.venv`, install `backend/requirements.txt`, and copy `backend/.env.example` to `backend/.env`. Supply a real `LITELLM_API_KEY` for the default provider and appropriate AWS credentials/profile/role.
2. Run `npm install` in `frontend/`, copy `frontend/.env.example` to `frontend/.env`, and set `VITE_API_BASE_URL` for the browser-accessible backend.
3. Run `./dev.sh`, or run Uvicorn on port 8000 and `npm run dev` on port 5173 separately. `docker compose up --build` is another checked-in development path. Both Dockerfiles and Compose run development reload servers.
4. Check `GET /api/health`, then `GET /api/config` and an allowed log-group discovery to validate configuration and AWS access. Health alone checks only process response.

Sources: `dev.sh`, both Dockerfiles, `docker-compose.yml`, both `.env.example` files, [root README](../README.md). Backend build uses Python 3.12 slim and `pip install`; frontend build uses Node 20 slim and `npm install`. The frontend production build command is `npm run build`, which runs TypeScript build plus Vite bundle; Compose does not serve that bundle.

## Staging and production

`deploy.sh` is the checked-in local production entry point. It requires `backend/.env`, Docker Compose v2, and curl; no public URL is required. It builds `backend/Dockerfile.prod` and `frontend/Dockerfile.prod` through `docker-compose.prod.yml`, recreates containers, and checks the locally proxied UI and `/api/health`. The frontend image uses `npm ci` and `npm run build`, then Nginx serves the static bundle and proxies `/api/*` including WebSockets. The backend image runs one Uvicorn process without reload. `deploy.sh` deploys the current checkout and does not pull Git or rewrite `.env`.

The production frontend binds only `127.0.0.1:${PROD_HTTP_PORT:-8080}` on the host; the backend has no published host port. A same-host process calls `http://127.0.0.1:${PROD_HTTP_PORT:-8080}/api`; a container attached to the `anomalog-prod_default` network calls `http://backend:8000/api`. Production Compose allows local browser origins at the selected port, while the UI uses same-origin `/api` calls. Remote hosts cannot use these endpoints without separate ingress; any future remote access needs its own TLS and caller access controls ([ASM-003](assumptions.md#asm-003)). The development Compose file still publishes 8000/5173 and uses reload servers.

## Environment, migration, and rollback

Required settings and optional provider/AWS/masking limits are in [configuration.md](configuration.md); IAM is in [iam_setup.md](iam_setup.md). Environment changes in Compose require container recreation to take effect. Database migrations are **Not currently applicable** because no database exists.

The production backend has a shallow container health check; `deploy.sh` checks only local UI and API response. It does not validate AWS identity, masking service, model endpoint, or Live Tail. No staging environment, CI/CD, or automatic rollback is checked in. Retain the previous image/commit and configuration for manual rollback; after restoring them, rerun `deploy.sh` and verify the local API, WebSocket upgrade where used, and an allowed AWS read. Do not test billable Live Tail automatically in CI.

## Production acceptance checks

- `bash -n deploy.sh` and `docker compose -f docker-compose.prod.yml config --quiet` pass with no public URL. The resulting configuration publishes only a loopback frontend port and no backend port.
- The built frontend serves `/`, proxies `/api/health`, and upgrades the Live Tail WebSocket for local browser use. A same-host process can call the loopback API; a container on `anomalog-prod_default` can call the backend service name. Neither endpoint is reachable from another host by default.
- Confirm the backend uses the intended IAM identity and can read one allowed log group while denying one unauthorized group. Health alone does not verify AWS access.
