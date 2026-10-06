# Frontend

## Framework, page, and layout

The frontend is React 18 with TypeScript and Vite (`frontend/package.json`). `frontend/src/main.tsx` mounts the single `App.tsx` page. No client router or additional pages are present. The header contains Anomalog and Model settings; the sidebar contains source selection, time range, and source-specific search controls; the main area contains the AI investigator, analytics dashboard, and log viewer. `frontend/src/App.css` has viewport breakpoints at 1180, 1050, 760, and 680 pixels; responsive layout exists in CSS, but no automated viewport test was found.

## Scope and ownership

The React and TypeScript app in `frontend/src/` is the browser interface for CloudWatch, CloudTrail, Live Tail, and AI investigation. `App.tsx` composes the source picker, search controls, investigator, analytics, and log viewer. `api/` owns HTTP types and calls, `hooks/` own request state, `state/selectionStore.ts` owns the current selection and loaded events, and `components/` own presentation and local interaction state.

The feature details live in [log-search.md](log-search.md), [live-tail.md](live-tail.md), [log-exploration.md](log-exploration.md), and [analysis.md](analysis.md). This file defines behavior shared across those features.

| Component | Feature | Role |
| --- | --- | --- |
| `SourceSelector/`, `TimeRangePicker/`, `FilterBar/` | FEATURE-001, FEATURE-002, FEATURE-003, FEATURE-004 | AWS source and query selection, Live Tail controls. |
| `LogViewer/LogViewer.tsx`, `LogFacetFilters.tsx`, `LogVolumeChart.tsx` | FEATURE-005 | Filter, virtualize, inspect, navigate, and export rows. |
| `LogViewer/AnalyticsDashboard.tsx` | FEATURE-005 | Status cards, trends, and findings. |
| `LogSummary/LogSummary.tsx`, `AnalysisResult.tsx` | FEATURE-006 | Question/chat/history and citation navigation. |
| `LogSummary/ModelSettingsControl.tsx`, `ModelSettingsPanel.tsx` | FEATURE-007 | Provider selection and connection test. |

`frontend/src/api/client.ts` uses Axios with `VITE_API_BASE_URL`; `api/types.ts` mirrors backend payloads. React Query handles remote query/mutation status (`hooks/`, `state/queryClient.ts`), Zustand owns selections and loaded events (`state/selectionStore.ts`), and component state owns temporary dialogs, filters, and chat interaction. Only completed investigation history is persisted to `localStorage`.

## Required behavior

- The browser talks to FastAPI through `VITE_API_BASE_URL`. It derives the Live Tail WebSocket URL from the same base and uses `wss://` when the API URL is HTTPS. Browser code does not access AWS credentials.
- The source selector switches between CloudWatch and CloudTrail. A source change clears loaded rows, pagination state, and highlighted lines and invalidates pending results from the previous source.
- Search controls require a selected source and valid time range. A new search replaces the current result; **Load more** appends using the returned cursor. Responses from superseded searches or an active Live Tail session cannot change the visible result.
- Loaded events have unique line indices for citations and navigation, including appended pages and Live Tail batches. The viewer filters, dashboard, chart, exports, and investigator operate on the appropriate loaded or visible subset described in the feature specs.
- The investigator submits only the currently visible rows, carries follow-up history, offers retry or stop on a failed or pending request, and links cited lines back to loaded events. Completed conversations are saved in browser local storage with a bounded history; deleting a saved conversation removes it from that store.
- Model settings keep each provider's key, model, and base URL separate. The UI identifies the destination for connection tests and analysis in Model settings. No server credential is exposed by `/api/config`.
- Starting Live Tail requires a cost confirmation. The browser shows session, sampling, paused buffer, dropped event, and estimated cost information while the backend controls the AWS stream. Leaving the page or changing sources closes the browser session.
- The interface communicates loading, empty, disabled, and error states for AWS reads and AI calls. Interactive controls remain keyboard reachable, and cited lines can be opened from the answer.

## Forms, feedback, and accessibility

CloudWatch search needs selected groups and a range no longer than seven days in the browser; backend validation remains authoritative. CloudTrail controls accept an optional account and lookup attribute; the account selector is disabled when `/api/config` reports no centralized account filtering. Model settings accepts provider-specific key/model/base URL values and shows the connection result. The investigator requires visible events and a nonblank question; it supports cancellation and retry. `frontend/src/components/FilterBar/` and `LogSummary/` implement these states.

The code uses native buttons, inputs, selects, and `<dialog>` for modal flows; several controls have ARIA labels, pressed/expanded states, and keyboard handlers. The log viewer is keyboard focusable and supports arrow navigation and Enter/Space highlighting. **Recommendation:** verify focus restoration, screen-reader announcements, color contrast, and narrow-screen usability manually; no accessibility audit or automated browser suite is present. See [testing.md](testing.md).

## Acceptance checks

- `cd frontend && npm run test && npm run lint && npm run build` succeeds.
- Current selection-store tests cover search invalidation, unique appended line indices, and bounded displayed Live Tail history. **Recommended:** add hook/browser tests that resolve an old HTTP response after a new search, source switch, or Live Tail start, and exercise paused-buffer behavior.
- A manual browser check covers source selection, search and **Load more**, facets and citations, provider switching, and Live Tail confirmation and stop. Live AWS or model traffic is optional for this check; unit tests use mocks.
