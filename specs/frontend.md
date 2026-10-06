# Frontend

## Scope and ownership

The React and TypeScript app in `frontend/src/` is the browser interface for CloudWatch, CloudTrail, Live Tail, and AI investigation. `App.tsx` composes the source picker, search controls, investigator, analytics, and log viewer. `api/` owns HTTP types and calls, `hooks/` own request state, `state/selectionStore.ts` owns the current selection and loaded events, and `components/` own presentation and local interaction state.

The feature details live in [log-search.md](log-search.md), [live-tail.md](live-tail.md), [log-exploration.md](log-exploration.md), and [analysis.md](analysis.md). This file defines behavior shared across those features.

## Required behavior

- The browser talks to FastAPI through `VITE_API_BASE_URL`. It derives the Live Tail WebSocket URL from the same base and uses `wss://` when the API URL is HTTPS. Browser code does not access AWS credentials.
- The source selector switches between CloudWatch and CloudTrail. A source change clears loaded rows, pagination state, and highlighted lines and invalidates pending results from the previous source.
- Search controls require a selected source and valid time range. A new search replaces the current result; **Load more** appends using the returned cursor. Responses from superseded searches or an active Live Tail session cannot change the visible result.
- Loaded events have unique line indices for citations and navigation, including appended pages and Live Tail batches. The viewer filters, dashboard, chart, exports, and investigator operate on the appropriate loaded or visible subset described in the feature specs.
- The investigator submits only the currently visible rows, carries follow-up history, offers retry or stop on a failed or pending request, and links cited lines back to loaded events. Completed conversations are saved in browser local storage with a bounded history; deleting a saved conversation removes it from that store.
- Model settings keep each provider's key, model, and base URL separate. The UI identifies the destination for connection tests and analysis in Model settings. No server credential is exposed by `/api/config`.
- Starting Live Tail requires a cost confirmation. The browser shows session, sampling, paused buffer, dropped event, and estimated cost information while the backend controls the AWS stream. Leaving the page or changing sources closes the browser session.
- The interface communicates loading, empty, disabled, and error states for AWS reads and AI calls. Interactive controls remain keyboard reachable, and cited lines can be opened from the answer.

## Acceptance checks

- `cd frontend && npm run test && npm run lint && npm run build` succeeds.
- Search generation tests cover a late result after a new search, source switch, or Live Tail start. Pagination and Live Tail append tests verify distinct line indices and bounded retained history.
- A manual browser check covers source selection, search and **Load more**, facets and citations, provider switching, and Live Tail confirmation and stop. Live AWS or model traffic is optional for this check; unit tests use mocks.
