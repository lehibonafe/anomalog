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
  HTTP status cards count `1xx` through `5xx`, using the status-code color
  scheme documented in the root README.
- **Log facets:** extract level, method, route, HTTP status, exception, and
  duration fields. Selecting a facet filters and highlights matching logs.
- **AI log summary:** becomes available when at least one log is listed. Line
  and range citations in a result are clickable and navigate to the referenced
  logs.
- **Model settings:** opens as a modal from the right side of the app header.
  LiteLLM is the default provider and its default server model is
  `qwen3.8-flash`.

## Live Tail UI

`src/components/FilterBar/LiveTailControls.tsx` owns the browser side of a Live
Tail session. Users must select 1–10 CloudWatch log groups and confirm the cost
dialog before the WebSocket is opened.

After AWS starts the session, the UI clears the historical result set and
appends masked live events. The event counter, elapsed timer, estimated cost,
facets, HTTP status cards, and analytics graph update as events arrive. AWS
sampling is shown as a warning because sampled counts are not exhaustive.

User activity is sent to the backend at most once every 30 seconds. The socket
is closed when the component unmounts or the page unloads. The backend remains
authoritative for inactivity timeouts, concurrency limits, stream closure, and
masking.

## Validation

```bash
npm run lint
npm run build
```

The project currently has no frontend test runner, so both commands are
required after UI changes.
