# Anomalog Frontend

The React and TypeScript interface for Anomalog, built with Vite. It supports
historical CloudWatch and CloudTrail searches, interactive log facets and
analytics, real-time CloudWatch Live Tail, and evidence-linked AI summaries.

See the repository [README](../README.md) for backend setup, AWS permissions,
Live Tail operations, and deployment guidance.

## Local development

```bash
npm install
cp .env.example .env
npm run dev
```

The default frontend URL is `http://localhost:5173`. Set
`VITE_API_BASE_URL` in `.env` to the browser-accessible FastAPI base URL:

```dotenv
VITE_API_BASE_URL=http://localhost:8000
```

For HTTPS deployments, use an HTTPS API URL. The Live Tail client derives a
secure `wss://` URL automatically.

## Interface behavior

- **Source selector:** switches between CloudWatch Logs and CloudTrail.
- **Historical search:** uses the selected time range and supports cursor-based
  **Load more** pagination.
- **Log analytics:** updates from the events currently loaded in the browser.
  HTTP status cards count a curated set of significant codes within `1xx`
  through `5xx`, display the included codes, and filter the raw logs when
  selected. Cards and facets use the same structured-field-first status
  extractor so their counts agree. A selected card also isolates its series in
  the HTTP trend graph. The exact code set is documented in the root README.
- **Log facets:** extract level, method, route, HTTP status, exception, and
  duration fields. The Status grid shows only the curated significant codes;
  its colors match the HTTP overview, and selecting a facet filters and
  highlights matching logs.
- **AI Log Investigator:** answers specific questions about the visible logs
  and carries context into follow-up questions. Line and range citations in an
  answer are clickable and navigate to the referenced logs.
- **Model settings:** opens as a modal from the right side of the app header.
  LiteLLM is the default provider. Recommended defaults are `qwen3.8-flash`
  for LiteLLM, `gemini-3.8-flash` for Gemini, `gpt-6-sol` for OpenAI,
  `claude-sonnet-5` for Anthropic, and `qwen3.5:9b` for Ollama.

## Live Tail UI

`src/components/FilterBar/LiveTailControls.tsx` owns the browser side of a Live
Tail session. Users must select 1–10 CloudWatch log groups and confirm the cost
dialog before the WebSocket is opened.

After AWS starts the session, the UI clears the historical result set and
appends masked live events. The event counter, elapsed timer, estimated cost,
facets, HTTP status cards, and analytics graph update as events arrive. AWS
sampling is shown as a warning because sampled counts are not exhaustive.

**Pause display** keeps the WebSocket and billable AWS session active while
holding up to 5,000 incoming events in the browser. **Resume** appends the
retained events to the viewer. When that buffer fills, the oldest paused events
are discarded and the UI reports the loss. Stopping a paused session flushes
the retained buffer before closing the stream.

User activity is sent to the backend at most once every 30 seconds. The socket
is closed when the component unmounts or the page unloads. The backend remains
authoritative for inactivity timeouts, concurrency limits, stream closure, and
masking.

## Validation

```bash
npm run lint
npm test
npm run build
```

Run all three commands after UI changes.
