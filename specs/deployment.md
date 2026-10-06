# Deployment

## Verified local development path

1. Create `backend/.venv`, install `backend/requirements.txt`, and copy `backend/.env.example` to `backend/.env`. Supply a real `LITELLM_API_KEY` for the default provider and appropriate AWS credentials/profile/role.
2. Run `npm install` in `frontend/`, copy `frontend/.env.example` to `frontend/.env`, and set `VITE_API_BASE_URL` for the browser-accessible backend.
3. Run `./dev.sh`, or run Uvicorn on port 8000 and `npm run dev` on port 5173 separately. `docker compose up --build` is another checked-in development path. Both Dockerfiles and Compose run development reload servers.
4. Check `GET /api/health`, then `GET /api/config` and an allowed log-group discovery to validate configuration and AWS access. Health alone checks only process response.

Sources: `dev.sh`, both Dockerfiles, `docker-compose.yml`, both `.env.example` files, [root README](../README.md). Backend build uses Python 3.12 slim and `pip install`; frontend build uses Node 20 slim and `npm install`. The frontend production build command is `npm run build`, which runs TypeScript build plus Vite bundle; Compose does not serve that bundle.

## Staging and production

**Not currently applicable as a verified, checked-in pipeline.** No staging environment, CI/CD workflow, production Dockerfile, reverse proxy configuration, certificate automation, or release manifest was found. The README describes an EC2 deployment and `./update-ec2.sh`/`deploy.sh`, but those scripts do not exist in this checkout. Treat those instructions as a documentation gap, not a runnable deployment contract. Any actual production infrastructure needs confirmation ([ASM-003](assumptions.md#asm-003)).

The README's stated desired production path requires HTTPS routing of `/api/*` including WebSockets to backend port 8000, frontend traffic to port 5173, browser API URL/CORS origin alignment, and external access control. These are **documented expectations**, not verified deployed resources. The current Compose file publishes ports directly and has no healthcheck stanza.

## Environment, migration, and rollback

Required settings and optional provider/AWS/masking limits are in [configuration.md](configuration.md); IAM is in [iam_setup.md](iam_setup.md). Environment changes in Compose require container recreation to take effect. Database migrations are **Not currently applicable** because no database exists.

No checked-in rollback automation or release validation pipeline exists. **Recommendation:** for a future production process, retain the previous image/commit and environment configuration, restore them on failure, recreate containers, verify `/api/health`, browser API reachability, WebSocket upgrade, and a permitted AWS read. This is a proposed procedure, not evidence of an existing one. Do not test billable Live Tail automatically in CI.
