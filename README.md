# Anomalog: AWS Log Intelligence Workspace

Anomalog is a web-based workspace for investigating AWS CloudWatch Logs
and CloudTrail events. Select log groups or CloudTrail lookup attributes,
choose a time range, and explore matching events through interactive
analytics and detailed filters. Generate an AI-powered summary of the visible
log slice, with citations that link each conclusion directly to its
supporting lines in the log viewer.

Supported LLM providers: **LiteLLM** (default — the team's internal proxy,
server-configured key/model/base URL) plus **Gemini**, **OpenAI**,
**Anthropic**, and **Ollama** (local), each opt-in per request via the UI's
Model settings. Only the LiteLLM key is required to boot.

## Architecture

- `backend/` — FastAPI service. Talks to AWS (boto3) and the LLM provider SDKs.
- `frontend/` — React + TypeScript (Vite) UI.

CloudWatch Live Tail uses a browser WebSocket connected to the FastAPI backend.
The backend owns the billable AWS stream, masks each event, and forwards only
the masked event to the browser. The browser never receives AWS credentials or
connects directly to CloudWatch.

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
   For real-time troubleshooting, select up to 10 CloudWatch log groups and
   choose **Start Live Tail**. Review the AWS cost confirmation before starting;
   the session stops after 15 minutes without user activity or immediately
   when the page disconnects.
3. Filter Log details as needed, then select **Generate summary** in the AI
   log summary card. Only the currently visible rows are analyzed; hidden and
   unloaded rows are excluded. The AI result is one evidence-linked sentence.
4. Select any cited line number in the summary to scroll to and highlight the
   supporting evidence in the log viewer.
5. To use Gemini/OpenAI/Anthropic/Ollama instead of the server's LiteLLM
   proxy, open **Model settings** in the app header and supply a
   provider + API key (Ollama needs a base URL instead).

## CloudWatch Live Tail

Live Tail is available only for CloudWatch Logs. It is separate from historical
search pagination: it streams new events as AWS provides them and does not have
a **Load more** action.

### Starting and stopping a session

1. Select between 1 and 10 CloudWatch log groups.
2. Optionally enter a CloudWatch Logs filter pattern.
3. Select **Start Live Tail** and review the confirmation dialog. No AWS session
   starts until you confirm.
4. Select **Stop Live Tail** when the investigation is complete.

When AWS confirms the session, Anomalog replaces the currently displayed logs
with the new live stream. Historical search, filter-pattern editing, and
pagination controls remain disabled until Live Tail stops. Closing the page,
switching away from the CloudWatch interface, or losing the browser connection
closes the backend AWS response stream.

The session panel shows:

- elapsed session time;
- the total number of live events received;
- estimated gross cost, rounded up by started minute and shown before any AWS
  free-tier allowance; and
- a warning when AWS indicates that a high-volume stream is being sampled.

The cost and free-tier values are display estimates. They do not change AWS
billing and should be updated if the account's AWS pricing differs.

### Inactivity and concurrency controls

The default inactivity timeout is 15 minutes and may be configured from 15 to
30 minutes. Inactivity means no pointer, keyboard, scroll, or touch activity in
the browser; incoming log events alone do not keep the session alive. Browser
activity is reported to the backend at most once every 30 seconds.

The backend allows three simultaneous Live Tail sessions by default. This
limit is per backend process, so a deployment with multiple workers has a total
potential limit of `workers × LIVE_TAIL_MAX_CONCURRENT_SESSIONS`. Use a single
worker or an external shared limiter if a deployment requires a strict
application-wide cap.

If the browser cannot consume the event stream quickly enough, the backend
stops the session instead of allowing the in-memory event buffer to grow
without bound. Stop and disconnect commands take priority over buffered log
events.

### Automatic HTTP status counting

Every received live event is appended to the same log store used by the
analytics dashboard. The HTTP status cards and trend chart therefore update
automatically while Live Tail is active:

| Range | Meaning | Color |
|-------|---------|-------|
| `1xx` | Informational | Purple |
| `2xx` | Success | Green |
| `3xx` | Redirection | Blue |
| `4xx` | Client Error | Amber |
| `5xx` | Server Error | Red |

The overview recognizes standalone three-digit values from `100` through `599`
in the masked log message. Each event is counted once in every status class it
contains, so one message containing both `401` and `500` contributes to both
cards. Numbers outside that range are ignored. Because the overview also uses a
plain-number fallback, an unrelated standalone number such as `404` can be
interpreted as an HTTP status; structured fields such as `status_code`,
`http.status_code`, and `response.status` are preferred for accurate facet
filtering.

The separate **Status** card counts operational words such as `Succeeded`,
`Started`, `Failed`, and `Resolved`; it is not the HTTP status-code count.

### Configuration

Set these values in `backend/.env`:

| Variable | Default | Purpose |
|----------|---------|---------|
| `LIVE_TAIL_MAX_CONCURRENT_SESSIONS` | `3` | Maximum active sessions per backend process; must be at least 1. |
| `LIVE_TAIL_INACTIVITY_TIMEOUT_SECONDS` | `900` | Browser inactivity timeout; accepted range is 900–1800 seconds. |
| `LIVE_TAIL_COST_PER_MINUTE_USD` | `0.01` | Display-only cost estimate used by the UI. |
| `LIVE_TAIL_FREE_TIER_MINUTES` | `1800` | Display-only monthly free-tier estimate used by the UI. |

Restart or recreate the backend after changing these values.

### WebSocket protocol

The UI connects to `ws://HOST/api/cloudwatch/logs/live-tail`, or `wss://` when
the configured API base URL uses HTTPS. The first client message must arrive
within 10 seconds:

```json
{
  "type": "start",
  "log_group_names": ["/aws/lambda/example"],
  "filter_pattern": "ERROR"
}
```

While connected, the client may send `{"type":"activity"}` to reset the
inactivity timer or `{"type":"stop"}` to end the session. Server messages use
the types `session_started`, `events`, `session_stopped`, `session_ended`, and
`error`. The backend validates the WebSocket `Origin` against `CORS_ORIGINS`,
and all event messages pass through the configured PII masker before delivery.

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
- Live Tail is denied unless the backend role is explicitly allowed to start
  and stop it. Scope the log-group resources to the groups Anomalog may access:

  ```json
  {
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": "logs:DescribeLogGroups",
        "Resource": "*"
      },
      {
        "Effect": "Allow",
        "Action": [
          "logs:FilterLogEvents",
          "logs:StartLiveTail",
          "logs:StopLiveTail"
        ],
        "Resource": "arn:aws:logs:REGION:ACCOUNT_ID:log-group:ALLOWED_PREFIX*"
      }
    ]
  }
  ```

  See [CloudWatch Live Tail](#cloudwatch-live-tail) for its runtime and cost
  configuration.
- `.env` changes require a container recreate (`docker compose up -d`), not
  `docker compose restart`.

## Tests

```bash
cd backend && source .venv/bin/activate
python -m pytest tests/
```

## Pagination and analysis coverage

Use **Load more** whenever a continuation cursor is available, including after
an empty AWS page. Searches return at most the requested limit without dropping
fetched events. CloudWatch shares the page budget across groups and carries
unvisited groups forward. CloudTrail keeps its AWS page size stable and may
return fewer events than requested to avoid overflowing the page budget. Keep
query parameters, including the limit, unchanged when continuing a search.
Results are sorted within each response; loading multiple pages does not imply
global chronological ordering across all groups or pages.

The AI summary reports loaded and submitted lines, lines in successfully
processed chunks, exclusions from filtering or sampling, omissions caused by
line/character/chunk limits, incomplete chunks, and shortened lines. Shortened
lines overlap with the scheduled line counts; they are not extra omitted lines.
“All submitted lines analyzed” means all submitted lines were processed without
omission or shortening, not that every matching AWS event was loaded or that the
AI conclusion is exhaustive. `lines_considered` counts lines scheduled in chunks;
`lines_not_analyzed` counts scheduled lines in failed or unattempted chunks.
