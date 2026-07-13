# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A local web app for investigating AWS CloudWatch Logs and S3-stored logs: pick a
source (log group(s), or bucket+prefix) and time range, view matching log lines,
and run a Google Gemini (free tier) analysis over the filtered slice that flags
errors/exceptions/stack traces/anomalies. Two services: `backend/` (FastAPI) and
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
                                                 ├── boto3 → CloudWatch Logs / S3
                                                 └── google-genai → Gemini API (free tier)
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

### The line-index contract (ties LLM findings back to on-screen log lines)

Every `LogEvent` (`backend/app/schemas/common.py`) carries a server-assigned
`line_index`, stable within one response. The frontend stores whatever
`LogEvent[]` a search/fetch returns and sends that *exact same array back
unchanged* to `POST /api/analysis/anomalies`. Every provider is prompted (via
the shared `build_prompt` in `services/llm/prompt.py`) to cite `line_index`
values from the bracketed line numbers, never invented ones, so a
`Finding.line_index_start/end` in the response always resolves against what's
currently rendered in `LogViewer` — no server-side session or cache needed to
keep them in sync. If you change how events are fetched/merged, preserve this:
`line_index` must be assigned once, in final display order, per response.

### CloudWatch multi-group search pagination

`cloudwatch_service.search_log_events` loops `filter_log_events` per log group
(there's no native AWS call that merges multiple log groups into one
time-ordered paginated stream), merges+sorts the results by timestamp, and
packs each group's remaining `nextToken` into a single opaque base64 JSON
`cursor` returned to the client. A group missing from that cursor dict means
it's exhausted and won't be queried again on the next page. If you need
large-scale/complex querying, CloudWatch Logs Insights (`start_query`) is the
noted upgrade path — not implemented here.

### S3 content fetching

`s3_service.fetch_object_content` streams `.gz` keys through
`gzip.GzipFile(fileobj=body)` and caps the **decompressed** byte count (not
raw compressed bytes) — capping raw gzip bytes mid-stream produces a corrupt-
stream error instead of a clean truncation. S3 time-range filtering
(`list_objects`) is client-side on `LastModified` after `list_objects_v2` —
there's no server-side date filter in that API, so very large prefixes should
be scoped with a tighter key prefix.

### Multi-provider LLM abstraction (`services/llm/` + `anomaly_service.py`)

Anomaly analysis supports four providers — Gemini, OpenAI, Anthropic, and
Ollama (local) — selected per-request via `AnalysisRequest.provider`
(defaults to `"gemini"`, matching pre-multi-provider behavior). Only Gemini
has a server-configured default key (`Settings.gemini_api_key`, required at
boot); the other three are purely opt-in via the frontend's "Model settings"
override fields (`AnomalyPanel.tsx`) — there are no required `Settings`
fields for them, so the app still boots with zero config beyond today's
Gemini key.

Each provider lives in `backend/app/services/llm/<name>_provider.py` and
implements the `LLMProvider` ABC (`services/llm/base.py`): constructed fresh
per `analyze()` call (never shared, so a frontend-supplied key never leaks
across requests), exposing `async call_chunk(prompt) -> ChunkResult` that
makes exactly one upstream call. Structured JSON output is handled
differently per provider's actual capabilities — don't assume they're
interchangeable:
- **Gemini**: native `response_schema` (the `ChunkResult` Pydantic class
  passed directly) via `google-genai`'s structured-output mode.
- **OpenAI**: `client.chat.completions.parse(response_format=ChunkResult)` —
  the SDK derives its own strict JSON schema from the Pydantic model
  internally (see gotcha below).
- **Anthropic**: forced tool-use (`tool_choice={"type":"tool","name":...}`),
  result read off the `tool_use` content block's `.input`.
- **Ollama** (`OllamaProvider(OpenAIProvider)`): reuses the OpenAI SDK
  pointed at `base_url="http://localhost:11434/v1"` (Ollama's compat layer),
  but plain JSON mode (`response_format={"type":"json_object"}`) + manual
  `ChunkResult.model_validate_json(...)` instead of `.parse()` — Ollama's
  compat layer doesn't reliably honor OpenAI's strict `json_schema` mode
  ([ollama/ollama#10001](https://github.com/ollama/ollama/issues/10001)).

**Gotcha**: `Finding`/`ChunkResult` (`schemas/analysis.py`) must stay plain
`BaseModel`s — do **not** add `model_config = ConfigDict(extra="forbid")` to
satisfy Anthropic's optional `strict: true` tool flag. That was tried and
broke Gemini: `extra="forbid"` makes `model_json_schema()` emit
`additionalProperties: false`, and Gemini's `response_schema` API rejects
that keyword outright (`400 INVALID_ARGUMENT ... Unknown name
"additional_properties"`). OpenAI's `.parse()` is unaffected either way — it
builds its own independent strict schema from the model regardless of
`extra`. Anthropic's forced `tool_choice` alone (without `strict`) is
reliable enough for this use case.

Orchestration (provider-agnostic, must not change per-provider) lives in
`AnomalyService.analyze` (`anomaly_service.py`, replaces the old
`gemini_service.py`/`GeminiAnomalyService`):

1. `log_filter.select_relevant` — regex-prefilters for
   `ERROR|WARN|FATAL|EXCEPTION|TRACEBACK|5xx|timeout|refused|denied` plus
   stack-frame patterns, keeping ±2 lines of context; falls back to even
   sampling if nothing matches (so quiet logs still get scanned).
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
   returns HTTP 200 with the partial findings plus a `warnings` entry —
   partial results are never discarded.

All log-volume tunables (caps, chunk size) live in `backend/app/config.py` as
`Settings` fields, sourced from `backend/.env`; per-provider RPM/retries/model
defaults live as constants in each `services/llm/<name>_provider.py`.

### Frontend state split

- **TanStack Query** owns all server calls (log groups, CloudWatch search,
  S3 listing/content, the analysis call as a `useMutation`) — see
  `frontend/src/hooks/`.
- **Zustand** (`frontend/src/state/selectionStore.ts`) owns cross-component UI
  state that isn't server state: current source/selection, the loaded
  `LogEvent[]`, and `highlightedRange`. This exists because `LogViewer` and
  `AnomalyPanel` are sibling components that both need the same loaded events
  and the currently-highlighted finding range.
- Clicking a `FindingCard` sets `highlightedRange` in the store;
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
