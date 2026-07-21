# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

**TraceMind** — a local web app for investigating AWS CloudWatch Logs and
CloudTrail events: pick a source (log group(s), or CloudTrail lookup
attributes) and time range, view matching log lines, and run an LLM analysis
over the filtered slice —
by default flagging errors/exceptions/stack traces/anomalies, or steered by an
optional user-supplied prompt (Gemini free tier by default; OpenAI/Anthropic/
Ollama opt-in per request). Two services: `backend/` (FastAPI) and
`frontend/` (React + TypeScript + Vite), run independently, no shared build step.

## Commands

### Backend (`backend/`)

```bash
python3 -m venv .venv && source .venv/bin/activate   # first time only
pip install -r requirements.txt                       # first time / after deps change
cp .env.example .env                                   # first time; fill in GEMINI_API_KEY

uvicorn app.main:app --reload --port 8000              # run dev server
python -m pytest tests/                                 # run all tests
python -m pytest tests/test_log_filter.py -v            # run one test file
python -m pytest tests/test_anomaly_service.py::test_analyze_returns_findings_from_single_chunk  # run one test
python -m pytest tests/services/llm/ -v                # run just the per-provider LLM tests
```

Tests must be invoked with `python -m pytest` (not bare `pytest`) or from within
the activated venv — `pytest.ini` sets `pythonpath = .` so `app.*` imports
resolve regardless, but the venv must be active for dependencies to be found.
`GEMINI_API_KEY` must be a non-empty string for `Settings` to construct (tests
use a dummy value like `test-key`; no real LLM calls happen in the test suite —
each provider test mocks that provider's own SDK client method with
`AsyncMock`, and `test_anomaly_service.py` monkeypatches either
`AnomalyService._call_chunk` or a provider class's `call_chunk`).

### Frontend (`frontend/`)

```bash
npm install              # first time / after deps change
cp .env.example .env     # first time
npm run dev              # Vite dev server on :5173
npm run build             # tsc -b && vite build — type-checks then bundles
npm run lint               # eslint .
```

### Run both at once

`./dev.sh` from the repo root backgrounds both servers (uvicorn on :8000, vite
on :5173) and kills both on exit.

### Docker

`docker compose up --build` runs both services. Both run in **dev mode with
hot reload**, not a production build: `backend/Dockerfile` runs
`uvicorn --reload`, `frontend/Dockerfile` runs `npm run dev -- --host 0.0.0.0`
(the `--host` flag is required — without it Vite only binds inside the
container's loopback and the host-mapped port is unreachable). `docker-compose.yml`
bind-mounts `backend/app` and `frontend/src` (+ `index.html`) into their
containers so local edits apply without rebuilding; it does *not* mount the
whole service directory, so `node_modules`/installed pip packages baked into
the image aren't clobbered by the mount. The backend container mounts the
host's `~/.aws` read-only to `/root/.aws` (container runs as root), and
`environment:` passes through `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/
`AWS_SESSION_TOKEN` from the host shell if exported before `docker compose up`
— same credential chain as running locally, described below. Both
`backend/.env` and `frontend/.env` must exist before `docker compose up`
(`env_file:` in the compose file, not baked into either image).

## Architecture

```
Browser (React/Vite, :5173) → axios (JSON) → FastAPI backend (:8000)
                                                 ├── boto3 → CloudWatch Logs / CloudTrail
                                                 └── provider SDKs → Gemini (default) /
                                                     OpenAI / Anthropic / Ollama
```

No database. No app-level auth — this is local-only, single-user; AWS
credentials and the Gemini API key are the real access boundary. The backend
is stateless per request except for one in-process Gemini rate limiter shared
across requests (see below).

### AWS auth (works unchanged local → deployed)

`backend/app/core/aws_session.py` builds a `boto3.Session` that only passes
`profile_name` when `AWS_PROFILE` is set in the environment; `AWS_PROFILE` is
blank by default in `backend/.env`. This matters because boto3's credential
chain only checks `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` env vars *before*
a named profile — if `AWS_PROFILE` is set, boto3 uses that profile and ignores
exported env vars entirely. So: exported access keys → leave `AWS_PROFILE`
blank; a named `~/.aws/credentials` profile → set `AWS_PROFILE` to it. When
this backend later runs on AWS compute, `AWS_PROFILE` stays unset and boto3
falls through further to the instance/task IAM role — no code path changes
between local dev and deployment.

One Docker-specific trap, now handled in code: docker compose's `env_file:`
exports the blank `AWS_PROFILE=` line as an *empty-string* env var, which
botocore reads directly (bypassing `Settings`) as a profile named `""` and
raises `ProfileNotFound: The config profile () could not be found`. This never
happens locally because pydantic reads `.env` without touching the process
environment. `get_boto3_session` therefore deletes an empty `AWS_PROFILE` from
`os.environ` before building the session — keep that behavior if you touch
`aws_session.py`.

### The line-index contract (ties LLM output back to on-screen log lines)

Every `LogEvent` (`backend/app/schemas/common.py`) carries a server-assigned
`line_index`, stable within one response. The frontend stores whatever
`LogEvent[]` a search/fetch returns and sends that *exact same array back
unchanged* to `POST /api/analysis/anomalies`. The shared `build_prompt`
(`services/llm/prompt.py`) tells the LLM to write a plain-language analysis
but to inline-cite `line_index` values from the bracketed line numbers when it
refers to specific lines (e.g. `[42]` or `[42-45]`), never invented ones. The
LLM's response is free text, not structured JSON — the frontend
(`AnalysisResult.tsx`) regex-matches those bracketed refs out of the text at
render time and turns each into a clickable element that sets
`highlightedRange`, so it always resolves against what's currently rendered in
`LogViewer` — no server-side session or cache needed to keep them in sync. If
you change how events are fetched/merged, preserve this: `line_index` must be
assigned once, in final display order, per response.

### Sensitive data masking

`services/masking.py::mask_message` is applied unconditionally to every
`LogEvent.message` at the source — inline in `cloudwatch_service.search_log_events`
and `cloudtrail_service.lookup_events`, before `line_index` is assigned. It
regex-redacts credentials/secrets (AWS access keys, JWTs, Bearer/Basic auth
headers, `password=`/`api_key=`/etc. key-value pairs) and PII (emails, SSNs,
phone numbers, credit card numbers validated via Luhn to avoid false-positiving
on arbitrary digit sequences like ports or IDs) to `***MASKED***`. There is no
config flag or per-request toggle to disable it — masking always runs before
data reaches the frontend or any LLM provider. Because it runs before
`line_index` assignment, the UI and the LLM always see the same (masked) text,
preserving the line-index contract above.

### CloudWatch time-range cap

`cloudwatch_service.search_log_events` rejects (`BadRequestError`, HTTP 400)
any request where `end_time - start_time` exceeds `Settings.max_time_range_days`
(default 7). `filter_log_events` itself isn't metered per-GB-scanned the way
CloudWatch Logs Insights queries are — it just reads data you've already paid
to ingest/store — but an unbounded range still means unbounded pagination,
more API calls, and a much larger response to process, so the cap keeps
queries and analysis runs bounded. The frontend mirrors this client-side
(`utils/time.ts::exceedsMaxTimeRange`, used in `TimeRangePicker` and
`CloudWatchSourcePicker`) to block the search button before the request fires;
the backend check is the actual enforcement point since the frontend one is
only a UX nicety.

### CloudWatch multi-group search pagination

`cloudwatch_service.search_log_events` loops `filter_log_events` per log group
(there's no native AWS call that merges multiple log groups into one
time-ordered paginated stream), merges+sorts the results by timestamp, and
packs each group's remaining `nextToken` into a single opaque base64 JSON
`cursor` returned to the client. A group missing from that cursor dict means
it's exhausted and won't be queried again on the next page. If you need
large-scale/complex querying, CloudWatch Logs Insights (`start_query`) is the
noted upgrade path — not implemented here.

### Multi-provider LLM abstraction (`services/llm/` + `anomaly_service.py`)

Analysis supports four providers — Gemini, OpenAI, Anthropic, and
Ollama (local) — selected per-request via `AnalysisRequest.provider`
(defaults to `"gemini"`, matching pre-multi-provider behavior).
`AnalysisRequest.user_prompt` (optional) swaps only the instruction block
inside the shared `build_prompt`: blank → the default anomaly/error scan;
set → the LLM answers the user's request instead. Both modes return the same
shape — free-form prose citing `line_index` values inline — so the
line-index contract and click-to-highlight work identically; don't fork the
output format per mode. Only Gemini has a server-configured default key
(`Settings.gemini_api_key`, required at boot); the other three are purely
opt-in via the frontend's "Model settings" override fields
(`AnomalyPanel.tsx`) — there are no required `Settings` fields for them, so
the app still boots with zero config beyond today's Gemini key.

Each provider lives in `backend/app/services/llm/<name>_provider.py` and
implements the `LLMProvider` ABC (`services/llm/base.py`): constructed fresh
per `analyze()` call (never shared, so a frontend-supplied key never leaks
across requests), exposing `async call_chunk(prompt) -> ChunkResult` that
makes exactly one upstream call and returns `ChunkResult(analysis: str)` —
plain text, not schema-validated JSON. The LLM is deliberately **not**
constrained to any structured output mode here (no `response_schema`,
`.parse()`, forced tool-use, or JSON mode) — each provider just takes
whatever plain-language text the model returns:
- **Gemini**: `generate_content(contents=prompt)`, `resp.text` wrapped as-is.
- **OpenAI**: `client.chat.completions.create(...)` (not `.parse()`),
  `completion.choices[0].message.content`.
- **Anthropic**: plain `messages.create(...)` with no `tools`/`tool_choice`,
  reads the first `text`-type content block.
- **Ollama** (`OllamaProvider(OpenAIProvider)`): inherits `call_chunk`
  unchanged from `OpenAIProvider` — Ollama's `/v1/chat/completions` is
  OpenAI-compatible and both now just want plain text back, so the provider
  only overrides `__init__`/`resolve_defaults` (for the localhost base_url
  and to not require an api_key). It used to need its own `call_chunk`
  override to avoid OpenAI's strict `json_schema` mode
  ([ollama/ollama#10001](https://github.com/ollama/ollama/issues/10001)),
  but that's moot now that nothing requests structured output at all.

Orchestration (provider-agnostic, must not change per-provider) lives in
`AnomalyService.analyze` (`anomaly_service.py`, replaces the old
`gemini_service.py`/`GeminiAnomalyService`):

1. `log_filter.select_relevant` — regex-prefilters for
   `ERROR|WARN|FATAL|EXCEPTION|TRACEBACK|5xx|timeout|refused|denied` plus
   stack-frame patterns, keeping ±2 lines of context; falls back to even
   sampling if nothing matches (so quiet logs still get scanned). **Skipped
   entirely when the request carries a `user_prompt`** — the regex is tuned to
   the anomaly scan and could drop the very lines a custom request asks about;
   volume is still bounded by steps 2–3.
2. `log_filter.truncate_and_cap` — per-line middle-truncation, then caps total
   lines/chars, preferring the most recent lines when over budget.
3. `log_filter.chunk` — splits into at most `gemini_max_chunks_per_analysis`
   chunks of `chunk_size_lines`; overflow is dropped and reported back via
   `lines_skipped_by_prefilter`/`warnings`, never silently.
4. Each chunk goes through a **process-wide, per-provider** `RateLimiter`
   (`core/rate_limiter.py`) — `AnomalyService` resolves one
   `ProviderDefaults`/`RateLimiter` pair per provider name at construction
   (Gemini's RPM/retries come from `Settings`; the other three are hardcoded
   constants in their own provider files), and the service itself is an
   `lru_cache`d singleton (`anomaly_service.get_anomaly_service`) so pacing
   holds across separate HTTP requests, not just within one `analyze()` call.
5. 429s get a short fixed backoff and retry (`AnomalyService._call_chunk`,
   catching the provider-internal `LLMRateLimited` signal); if the *first*
   chunk exhausts quota, the whole request raises `LLMQuotaExceededError`
   (→ HTTP 429); if quota runs out *after* some chunks succeeded, the request
   returns HTTP 200 with the partial analysis text (each successful chunk's
   text joined with blank lines) plus a `warnings` entry — partial results
   are never discarded.

All log-volume tunables (caps, chunk size) live in `backend/app/config.py` as
`Settings` fields, sourced from `backend/.env`; per-provider RPM/retries/model
defaults live as constants in each `services/llm/<name>_provider.py`.

### Frontend state split

- **TanStack Query** owns all server calls (log groups, CloudWatch search,
  CloudTrail lookup, the analysis call as a `useMutation`) — see
  `frontend/src/hooks/`.
- **Zustand** (`frontend/src/state/selectionStore.ts`) owns cross-component UI
  state that isn't server state: current source/selection, the loaded
  `LogEvent[]`, and `highlightedRange`. This exists because `LogViewer` and
  `AnomalyPanel` are sibling components that both need the same loaded events
  and the currently-highlighted range.
- `AnalysisResult.tsx` regex-extracts bracketed `line_index` refs (e.g. `[42]`,
  `[42-45]`) out of the LLM's free-text analysis and renders each as a
  clickable element; clicking one sets `highlightedRange` in the store.
  `LogViewer` reacts to that via `useEffect` and calls the react-window `List`
  imperative API (`useListRef().current.scrollToRow(...)`) to scroll to and
  highlight the matching lines. Note: this project uses **react-window v2**,
  whose API (`List` + `rowComponent`/`rowProps`/`rowHeight`, `useListRef`) is
  a full rewrite from v1's `FixedSizeList` — don't reach for v1 patterns.

## Environment notes

- Node in this environment is 18.20.8. The latest `create-vite`/`eslint`
  toolchain requires Node ≥20 (`node:util` `styleText` export); if you ever
  need to re-scaffold, use `npm create vite@5` rather than the latest major.
- Docker images use their own Node/Python versions (node:20-slim,
  python:3.12-slim) independent of the host — the Node 18 constraint above
  only applies to commands run directly on this host.
