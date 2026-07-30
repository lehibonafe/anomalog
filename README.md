# TraceMind

Local web app for investigating AWS CloudWatch Logs and CloudTrail events: pick
a source (log groups, or CloudTrail lookup attributes) and a time range,
browse the matching log lines, then run an LLM analysis over the filtered
slice — either the default error/anomaly scan, or a custom prompt ("find all
failed logins for user X"). Findings cite line numbers and click-to-highlight
the matching lines in the viewer.

Supported LLM providers: **LiteLLM** (default — the team's internal proxy,
server-configured key/model/base URL) plus **Gemini**, **OpenAI**,
**Anthropic**, and **Ollama** (local), each opt-in per request via the UI's
Model settings. Only the LiteLLM key is required to boot.

## Architecture

- `backend/` — FastAPI service. Talks to AWS (boto3) and the LLM provider SDKs.
- `frontend/` — React + TypeScript (Vite) UI.

The backend uses boto3's default credential chain, checked in this order:
`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` env vars (e.g. `export`ed in your
shell) → the `AWS_PROFILE` named profile from `~/.aws/credentials` (only if
set in `backend/.env`; it's blank by default) → the instance/task IAM role
when deployed onto AWS compute. Leave `AWS_PROFILE` blank if you export keys
directly — setting it forces boto3 to use that profile instead, ignoring
exported env vars. (An empty `AWS_PROFILE` is treated as unset, including when
Docker exports the blank line as an empty env var.)

Every log line is masked for credentials/secrets/PII (`backend/app/services/masking.py`)
before it reaches the UI or any LLM — via an external masking service when
`MASKING_SERVICE_API_KEY` is set (falling back to local regex masking on any
failure), or local regex masking only otherwise. This isn't configurable per
request; it always runs.

LLM free tiers have real rate/quota limits, so before any log slice is sent to
a model the backend prefilters for errors/exceptions/stack traces, caps total
lines/characters, and chunks + paces requests per provider (see
`backend/app/services/log_filter.py` and `anomaly_service.py`). When you
supply a custom prompt, the error-keyword prefilter is skipped — otherwise it
could drop the very lines your prompt asks about — but the caps and pacing
still apply.

## Setup

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in LITELLM_API_KEY (Gemini/OpenAI/Anthropic/Ollama are opt-in, no key needed to boot)
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
```

## Running

Two terminals:

```bash
# terminal 1
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000

# terminal 2
cd frontend && npm run dev
```

Or from the repo root, run both at once:

```bash
./dev.sh
```

Then open http://localhost:5173.

### Or with Docker

```bash
docker compose up --build
```

Runs both services in dev mode with hot reload — `backend/app` and
`frontend/src` are bind-mounted into their containers, so local edits apply
without rebuilding. The backend container mounts your host `~/.aws` read-only
(for profile-based auth) and also passes through `AWS_ACCESS_KEY_ID`/
`AWS_SECRET_ACCESS_KEY`/`AWS_SESSION_TOKEN` from your shell if you `export`ed
them before running `docker compose up` — same credential chain as running
locally. Requires `backend/.env` and `frontend/.env` to already exist (see
Setup above).

Then open http://localhost:5173.

## Usage

1. Pick a source in the sidebar: CloudWatch log group(s), or CloudTrail
   lookup attributes.
2. Set a time range and load the logs. Keep ranges narrow — everything is
   fetched through paginated AWS reads.
3. (Optional) Type a prompt in the analysis panel to steer the LLM; leave it
   blank for the default error/anomaly scan.
4. Click **Analyze logs**. Each finding cites the log lines it's based on —
   click a finding card to scroll to and highlight those lines.
5. To use Gemini/OpenAI/Anthropic/Ollama instead of the server's LiteLLM
   proxy, open **Model settings** in the analysis panel and supply a
   provider + API key (Ollama needs a base URL instead).

## Deploying on a remote host (e.g. EC2)

The app has **no authentication** — restrict access at the network layer
(security group scoped to your IP, VPN, or an authenticated reverse proxy).
There is a lightweight per-IP inbound rate limit (`INBOUND_RATE_LIMIT_PER_MINUTE`,
default 120/min) as an abuse guard, but it's not a substitute for real access
control, and it's per-worker — see `backend/app/core/rate_limiter.py`. Beyond
that:

- `VITE_API_BASE_URL` (`frontend/.env`) and `CORS_ORIGINS` (`backend/.env`)
  are **browser-facing** values: set them to the host's public address, not
  `localhost`, and keep them consistent with the exact origin you browse from.
- On EC2, prefer an instance IAM role over exported keys: leave `AWS_PROFILE`
  unset and attach CloudWatch Logs/CloudTrail read policies to the role. If the
  backend runs in Docker, raise the IMDS hop limit so the container can reach
  role credentials:
  `aws ec2 modify-instance-metadata-options --http-put-response-hop-limit 2`.
- `.env` changes require a container recreate (`docker compose up -d`), not
  `docker compose restart`.

## Tests

```bash
cd backend && source .venv/bin/activate
python -m pytest tests/
```
