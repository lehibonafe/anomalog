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

Recommended defaults balance investigation quality, latency, and cost:

| Provider | Default model |
|----------|---------------|
| LiteLLM | `qwen3.8-flash` |
| Gemini | `gemini-3.8-flash` |
| OpenAI | `gpt-6-sol` |
| Anthropic | `claude-sonnet-5` |
| Ollama | `qwen3.5:9b` |

The model field in the UI may override these values per request. Gemini and
LiteLLM defaults may also be changed server-side with `GEMINI_MODEL` and
`LITELLM_MODEL`.

## Architecture

- `backend/` — FastAPI service. Talks to AWS (boto3) and the LLM provider SDKs.
- `frontend/` — React + TypeScript (Vite) UI.

Behavior specifications live in [`specs/`](specs/README.md). The app's HTTP and
WebSocket contract is in [`api-reference.md`](api-reference.md); the similarly
named `api-reference_1.md` covers the separate PII masking service.

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
a model the backend prefilters for errors/exceptions/stack traces, significant
HTTP statuses (`401`, `403`, `408`, `429`, and `5xx`), caps total
lines/characters, and chunks + paces requests per provider (see
`backend/app/services/log_filter.py` and `anomaly_service.py`). Custom prompts
use their own query-aware selector, with an anomaly-focused fallback when the
question has no direct lexical matches.

Focused investigator questions use question-aware retrieval with nearby context
instead of sending every visible row. Before each model call, JSON messages are
minified without dropping fields, equivalent repetitive entries are represented
by a counted source line, recognized HTTP/service totals are calculated locally,
conversation history is trimmed to a token budget, and the total evidence
payload is capped with a conservative tokenizer-independent estimate. The
response's analysis notes show source-log coverage, compact evidence rows, and
estimated input tokens.

The relevant backend controls are `MAX_ANALYSIS_TOKENS` (default `40000`),
`MAX_CHAT_HISTORY_TOKENS` (default `4000`), and `MAX_LLM_OUTPUT_TOKENS`
(default `2048`). LiteLLM Qwen reasoning is disabled by default through
`LITELLM_ENABLE_THINKING=false`. Gemini 3 uses
`GEMINI_THINKING_LEVEL=low` for latency-sensitive log analysis; the legacy
`GEMINI_THINKING_BUDGET` setting applies only when explicitly selecting a
Gemini 2.5 model.

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

Press Ctrl+C once to stop both services, including their reload worker
processes.

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
3. Filter Log details as needed, then ask a specific question in the **AI Log
   Investigator**, such as “Who shut down the EC2 instance?” or “Which service
   has the most 5xx errors?” Only currently visible rows are analyzed; hidden
   and unloaded rows are excluded. Follow-up questions retain the conversation
   context.
4. Select any cited line number in an answer to scroll to and highlight the
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
4. Select **Pause display** to temporarily hold incoming events out of the log
   viewer. Select **Resume** to append the buffered events.
5. Select **Stop Live Tail** when the investigation is complete.

When AWS confirms the session, Anomalog replaces the currently displayed logs
with the new live stream. Historical search, filter-pattern editing, and
pagination controls remain disabled until Live Tail stops. Closing the page,
switching away from the CloudWatch interface, or losing the browser connection
closes the backend AWS response stream.

Pausing affects the browser display only: the AWS session remains connected and
billable, the elapsed timer continues, and the normal inactivity timeout still
applies. The browser buffers up to 5,000 events while paused. Resuming appends
the retained events to the viewer; if the buffer fills, the oldest paused
events are discarded and the session panel reports how many were lost. Stopping
while paused flushes the retained buffer before closing the AWS stream.

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

| Range | Included codes | Meaning | Color |
|-------|----------------|---------|-------|
| `1xx` | `100`, `101` | Informational | Purple |
| `2xx` | `200`, `201`, `202`, `204` | Success | Green |
| `3xx` | `301`, `302`, `304`, `307`, `308` | Redirection | Blue |
| `4xx` | `400`, `401`, `403`, `404`, `408`, `409`, `422`, `429` | Client Error | Amber |
| `5xx` | `500`, `502`, `503`, `504` | Server Error | Red |

The overview and **Log facets → Status** grid share the same status extractor
and curated code set, so their counts reconcile. The extractor prefers
structured fields such as `status_code`, `http.status_code`, and
`response.status`; otherwise it uses the first status-like standalone number
in the message. Each event contributes to at most one HTTP status. Other codes
in the same ranges are ignored.

The raw log viewer continues to retain every loaded event.
Selecting an HTTP status card filters the raw logs and volume graph and shows
only that status family's series in the HTTP trend graph. Selecting the active
card again restores all series.

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

## Deploying locally on an EC2 host

This section is for `./deploy.sh`, which uses the production configuration even
though its API listens only on the local host. `./dev.sh` does not require an
Anomalog API key when `ANOMALOG_API_KEY` is unset.

Push the code and [`backend/.env.example`](backend/.env.example) to the
repository. Do **not** push `backend/.env`: Git ignores it, and it must contain
the secrets for each deployment host. After cloning or pulling the repository
on the production EC2 host:

1. On a new host, create the private configuration file:

   ```bash
   cp backend/.env.example backend/.env
   chmod 600 backend/.env
   ```

   Keep an existing `backend/.env` when pulling later updates; a Git pull does
   not replace this ignored file.

2. Generate the Anomalog machine key on the production host:

   ```bash
   openssl rand -hex 32
   ```

   Put the output in the `ANOMALOG_API_KEY=` line of `backend/.env`. You create
   this key yourself; AWS and the LiteLLM provider do not issue it. Never put
   the value in `.env.example`, a commit, the frontend build, or a chat message.
   The key must be at least 32 characters. `deploy.sh` checks that it is set.

3. Give the **same** key to the other app through its server-side secret
   configuration. That app sends it as the `X-API-Key` header on every Anomalog
   API request and Live Tail WebSocket handshake. Set `LITELLM_API_KEY` in
   `backend/.env` separately if you use default model analysis; configure the
   AWS region and instance/assumed role as described below. The Anomalog key
   grants API access; the LiteLLM key grants access to the model proxy.

4. Deploy from the checked-out repository on the EC2 host:

   ```bash
   ./deploy.sh
   ```

`deploy.sh` builds the production images from the current checkout, recreates
both containers, and checks the local UI and API health endpoint. It does not
edit `backend/.env` or pull Git changes. The frontend is a static build served
by Nginx; the backend runs Uvicorn without reload. The frontend uses same-origin
`/api` requests, including the Live Tail WebSocket, but the included browser UI
cannot authenticate to the protected production API. Production is configured
for the other app's backend to call it. No public URL, DNS record, or HTTPS
proxy is required for another backend on the same EC2 host or Docker network.

Only `127.0.0.1:8080` is published on the host. The backend is reachable only
inside the Compose network. Use `PROD_HTTP_PORT` to change the loopback port:

```bash
PROD_HTTP_PORT=8081 ./deploy.sh
```

An app running directly on the same EC2 host calls
`http://127.0.0.1:8080/api/...`. A container on the `anomalog-prod_default`
Docker network calls `http://backend:8000/api/...`. A container in another
Compose project can join that network by declaring it as external:

```yaml
services:
  other-app:
    networks: [anomalog]
networks:
  anomalog:
    external: true
    name: anomalog-prod_default
```

The calling app must send `X-API-Key` on each HTTP request and Live Tail
WebSocket handshake. For example, a same-host health check is public, while
configuration requires the key:

```bash
curl -H "X-API-Key: $ANOMALOG_API_KEY" http://127.0.0.1:8080/api/config
```

Load `ANOMALOG_API_KEY` into the calling app from its secret store before using
that example; do not put it in source code. An unauthenticated request to
`/api/config` must return 401, and an authenticated request must return 200.
Only processes on the EC2 host and containers attached to this Docker network
can reach the default deployment.
Do not publish port 8000 or forward port 8080 to other hosts without TLS and
network access controls. The local health check does not prove AWS permissions;
verify an allowed log read separately.

When the EC2 instance is in account A and the monitoring account is account B,
set these values in `backend/.env` to assume a read role in B and enable
linked-account discovery:

```dotenv
AWS_ROLE_ARN=arn:aws:iam::MONITORING_ACCOUNT_ID:role/AnomalogMonitoringReadRole
AWS_INCLUDE_LINKED_ACCOUNTS=true
```

Set `AWS_ROLE_EXTERNAL_ID` too when the role trust policy requires it. The
deployment script preserves these values by leaving `.env` untouched. Verify
the assumed AWS identity and an allowed log read after deployment.

The account A EC2 instance role needs permission to assume only the monitoring
role:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "sts:AssumeRole",
    "Resource": "arn:aws:iam::MONITORING_ACCOUNT_ID:role/AnomalogMonitoringReadRole"
  }]
}
```

The account B role's trust policy must name the exact account A instance role:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "AWS": "arn:aws:iam::APPLICATION_ACCOUNT_ID:role/AnomalogEc2Role"
    },
    "Action": "sts:AssumeRole"
  }]
}
```

The role in account B also needs the CloudWatch permissions shown below. When
`AWS_INCLUDE_LINKED_ACCOUNTS=true`, log-group discovery includes groups shared
with B through CloudWatch cross-account observability. The UI uses each group's
ARN for searches and Live Tail, labels the owning account ID, and can load
every page rather than stopping at the first 50 groups.

CloudWatch Logs *centralization* is different: it copies new events into log
groups owned by B. Those copied groups therefore display B's account ID. Use a
destination naming pattern containing `${source.accountId}`, such as
`/centralized/${source.accountId}${source.logGroup}`, when the source account
must remain identifiable in the app.

With `AWS_INCLUDE_LINKED_ACCOUNTS=true`, the CloudTrail tab automatically
discovers the six ETAP CloudTrail log groups in the monitoring account and its
OAM-linked source accounts. It searches the selected account's group or all six
groups, preserves its attribute filters, and labels each event from its
`recipientAccountId` and `awsRegion`. The monitoring role needs
`logs:DescribeLogGroups` and `logs:FilterLogEvents`. Set
`CLOUDTRAIL_LOG_GROUP_IDENTIFIERS` to a comma-separated list of CloudWatch Logs
group names or ARNs only when an explicit override is needed. If linked-account
mode and the override are both unset, the tab falls back to `LookupEvents`,
which AWS limits to the assumed account's current Region and 90-day event
history.

The CloudTrail account selector defaults to **All accounts** and can restrict a
search to ETAP DEVOPS, ECPAY, INC, MONITORING, SRE, or SYSOPS. Account filtering
uses the CloudTrail event's `recipientAccountId` field and therefore requires
the centralized CloudWatch Logs mode.

Production uses a shared machine API key; it does not identify individual
users. There is a lightweight per-IP inbound rate limit (`INBOUND_RATE_LIMIT_PER_MINUTE`,
default 120/min) as an abuse guard, but it's not a substitute for real access
control, and it's per-worker — see `backend/app/core/rate_limiter.py`. Beyond
that:

- The included browser UI uses same-origin API calls but has no production
  sign-in flow. Use the server-to-server API in production. Development still
  uses `frontend/.env` and `backend/.env` for `VITE_API_BASE_URL` and `CORS_ORIGINS`.
- On EC2, prefer an instance IAM role over exported keys and leave
  `AWS_PROFILE` unset. For a same-account deployment, attach the read policy
  directly. For the account A/account B deployment, use the restricted
  `sts:AssumeRole` permission described above and attach the read policy to the
  account B role. If the backend runs in Docker, raise the IMDS hop limit so
  the container can reach role credentials:
  `aws ec2 modify-instance-metadata-options --http-put-response-hop-limit 2`.
- Live Tail is denied unless the backend role is explicitly allowed to start
  and stop it. The monitoring role also needs OAM read permissions to discover
  source-account links. Scope the log-group resources to the groups Anomalog
  may access. `logs:StopLiveTail` and the regional CloudTrail fallback
  `cloudtrail:LookupEvents` require wildcard resource scope, separate from
  log-group-scoped permissions:

  ```json
  {
    "Version": "2012-10-17",
    "Statement": [
      {
        "Effect": "Allow",
        "Action": [
          "oam:Get*",
          "oam:List*"
        ],
        "Resource": "*"
      },
      {
        "Effect": "Allow",
        "Action": "logs:DescribeLogGroups",
        "Resource": "*"
      },
      {
        "Effect": "Allow",
        "Action": [
          "logs:FilterLogEvents",
          "logs:StartLiveTail"
        ],
        "Resource": "arn:aws:logs:REGION:ACCOUNT_ID:log-group:ALLOWED_PREFIX*"
      },
      {
        "Effect": "Allow",
        "Action": ["logs:StopLiveTail", "cloudtrail:LookupEvents"],
        "Resource": "*"
      }
    ]
  }
  ```

  See [IAM setup](specs/iam_setup.md) for mode-specific policy guidance and
  [CloudWatch Live Tail](#cloudwatch-live-tail) for runtime and cost settings.
- After editing `backend/.env`, rerun `./deploy.sh`
  to recreate the production containers with the new values.

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
