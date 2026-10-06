# Features

Feature IDs are stable and link to [requirements.md](requirements.md). These sections summarize the complete user-visible capabilities; detailed constraints live in the linked feature specs.

## FEATURE-001 — Log-group discovery

### Purpose
Let an operator find selectable CloudWatch groups, including linked-account groups when configured.
### User story
As an operator, I want to search and page through groups so I can choose the right log sources.
### Preconditions
Backend has AWS credentials and `logs:DescribeLogGroups`; linked groups require external AWS sharing and `AWS_INCLUDE_LINKED_ACCOUNTS`.
### Workflow
Type keyword → debounced `GET /api/cloudwatch/log-groups` → select identifiers → optionally load another group page.
### Business rules
The API requests 1–50 groups per page; group ARN and owner ID are retained when AWS returns them.
### Inputs
`keyword` or compatibility `prefix`, `next_token`, `limit`.
### Outputs
`log_groups[]` and `next_token`.
### Error cases
AWS discovery failure appears as a picker error; no group means an empty state.
### Edge cases
Linked groups use ARN identifiers, and group names may repeat across accounts.
### Security considerations
Discovery exposes allowed group names and account IDs to anyone who can reach the API.
### Acceptance criteria
Matching groups remain selectable across pages; linked owner labels and identifiers are preserved.
### Related requirements
REQ-FUNC-001, REQ-OPS-002.
### Related components
`frontend/src/components/SourceSelector/CloudWatchSourcePicker.tsx`, `frontend/src/hooks/useLogGroups.ts`, `backend/app/services/cloudwatch_service.py`; [log-search.md](log-search.md).

## FEATURE-002 — CloudWatch historical search

### Purpose
Retrieve masked events from selected groups over a bounded time range.
### User story
As an investigator, I want filtered historical logs so I can trace an incident.
### Preconditions
One or more selected groups, valid start/end input, AWS read permission.
### Workflow
Set range and optional filter pattern → search → inspect results → load cursor pages.
### Business rules
The backend caps range and response lines, masks messages, merges groups oldest-first, and binds continuation to query inputs.
### Inputs
`CloudWatchSearchRequest` in [api.md](api.md).
### Outputs
Masked `LogEvent[]`, `cursor`, `truncated`, `total_returned`.
### Error cases
Too-large range or invalid cursor returns 400; Pydantic shape errors return 422; AWS failures may return 500.
### Edge cases
An empty AWS page can still carry a cursor; late responses must not replace a newer search.
### Security considerations
Cursor content is not signed; see [security.md](security.md).
### Acceptance criteria
Interleaved groups remain ordered without lost events; stale results are ignored.
### Related requirements
REQ-FUNC-002, REQ-FUNC-004, REQ-FUNC-005, REQ-SEC-001, REQ-PERF-001.
### Related components
`backend/app/services/cloudwatch_service.py`, `group_pagination.py`, `frontend/src/hooks/useCloudWatchSearch.ts`; [log-search.md](log-search.md).

## FEATURE-003 — CloudTrail search

### Purpose
Inspect AWS API activity through centralized logs or regional event history.
### User story
As an operator, I want to filter CloudTrail events by account and attribute when available so I can explain changes.
### Preconditions
Centralized/linked groups or `cloudtrail:LookupEvents`; account selection requires centralized mode.
### Workflow
Select CloudTrail, range, optional account and attribute → search → load cursor pages.
### Business rules
Configured or linked CloudWatch groups take precedence; fallback uses regional `LookupEvents`. Centralized pages are oldest-first; regional pages newest-first.
### Inputs
`CloudTrailSearchRequest` in [api.md](api.md).
### Outputs
Masked events with event name, origin, timestamp, and cursor.
### Error cases
Missing discovered account group, unsupported account selection, range, or cursor problems return client errors; AWS failures may return 500.
### Edge cases
Regional lookup may return fewer than requested because AWS page size is 50; account labels in picker are configured for six IDs.
### Security considerations
CloudTrail content includes identities and account information; masking applies before UI delivery.
### Acceptance criteria
Both modes and ordering are preserved; unavailable account filtering is disabled in UI.
### Related requirements
REQ-FUNC-003, REQ-FUNC-004, REQ-FUNC-005, REQ-SEC-001.
### Related components
`backend/app/services/cloudtrail_service.py`, `frontend/src/components/SourceSelector/CloudTrailSourcePicker.tsx`; [log-search.md](log-search.md).

## FEATURE-004 — CloudWatch Live Tail

### Purpose
Show new CloudWatch events while an investigation is active.
### User story
As an operator, I want a live stream with a clear cost prompt and stop control so I can watch an incident safely.
### Preconditions
CloudWatch mode, 1–10 selected groups, WebSocket access, AWS Live Tail permission.
### Workflow
Review cost dialog → confirm → start WebSocket/AWS stream → optionally pause/resume → stop or disconnect.
### Business rules
Backend owns AWS stream and masking; per-process session cap, inactivity timeout, bounded queue; browser pause buffer 5,000 and displayed history 10,000.
### Inputs
WebSocket `start`, `activity`, `stop` messages.
### Outputs
`session_started`, `events`, terminal messages, UI estimates and counters.
### Error cases
Invalid start, session cap, AWS error, slow consumer, or forbidden Origin terminates or rejects session.
### Edge cases
Pausing remains billable; old paused/displayed rows can be discarded with counts shown.
### Security considerations
Origin validation is not user authentication; event text is masked before send.
### Acceptance criteria
No AWS start before confirmation; stop/disconnect closes stream; dropped counts remain visible.
### Related requirements
REQ-FUNC-006, REQ-FUNC-007, REQ-REL-001, REQ-SEC-001, REQ-PERF-001.
### Related components
`frontend/src/components/FilterBar/LiveTailControls.tsx`, `backend/app/api/routes_cloudwatch.py`, `backend/app/services/live_tail_service.py`; [live-tail.md](live-tail.md).

## FEATURE-005 — Log exploration and export

### Purpose
Turn loaded rows into a navigable, filterable investigation view.
### User story
As an investigator, I want facets, charts, highlights, and export so I can isolate and share evidence.
### Preconditions
Loaded historical or live events.
### Workflow
Choose keyword/facet/finding → inspect chart and rows → expand JSON, navigate line, or export visible rows.
### Business rules
Viewer uses virtualized rows; facets favor structured fields; significant HTTP-code list is curated; export reflects filtered rows.
### Inputs
Loaded `LogEvent[]`, keyword, facets, finding, citation line.
### Outputs
Dashboard/chart, filtered rows, JSON/CSV/text download.
### Error cases
No loaded or matching rows shows an empty state; failed pagination shows retry text.
### Edge cases
Appended pages preserve filters; cited line may be unloaded or excluded by current filters.
### Security considerations
CSV formula prefixes are escaped; exported and locally displayed data are subject to masking limits.
### Acceptance criteria
Counts update with appended/live rows, filters agree with AI input, and cited loaded lines can be reached.
### Related requirements
REQ-FUNC-008, REQ-FUNC-009, REQ-FUNC-010, REQ-SEC-004, REQ-PERF-002.
### Related components
`frontend/src/components/LogViewer/`, `frontend/src/utils/logFacets.ts`; [log-exploration.md](log-exploration.md).

## FEATURE-006 — AI investigation

### Purpose
Answer questions about the currently visible log slice with evidence and coverage diagnostics.
### User story
As an investigator, I want an answer tied to log lines so I can evaluate it against source evidence.
### Preconditions
At least one visible event and a working provider configuration.
### Workflow
Ask question → submit visible rows/history → backend re-masks and selects evidence → provider calls → show answer, warnings, citations → optionally follow up or save conversation.
### Business rules
Request event/history caps, token and chunk budgets, provider pacing; completed conversations saved locally, up to 20.
### Inputs
`AnalysisRequest`; optional provider overrides and history.
### Outputs
`AnalysisResponse` with answer, counts, model, warnings; browser history entry.
### Error cases
Bad input 400/422, first-chunk quota 429, provider failure 502, or partial answer with warnings.
### Edge cases
No direct lexical match falls back to anomaly retrieval; later chunk failure may still yield partial answer.
### Security considerations
Request messages are locally re-masked before model calls; question/history may still contain sensitive text if typed by user.
### Acceptance criteria
Only visible rows are submitted; provider and coverage are accurate; citations navigate to loaded lines when present.
### Related requirements
REQ-FUNC-011, REQ-FUNC-013, REQ-SEC-002, REQ-REL-003.
### Related components
`frontend/src/components/LogSummary/`, `backend/app/services/anomaly_service.py`, `log_filter.py`; [analysis.md](analysis.md).

## FEATURE-007 — Model settings and connection test

### Purpose
Choose a provider and check its configured destination before analysis.
### User story
As an investigator, I want provider-specific settings so I can use an approved model without mixing credentials.
### Preconditions
Backend reachable; provider key or base URL supplied where required.
### Workflow
Open header settings → select provider → enter optional key/model/base URL → test connection → analyze.
### Business rules
LiteLLM is default; settings remain separate in browser memory by provider; test performs a small provider call and reports success or failure.
### Inputs
`TestConnectionRequest` or analysis provider overrides.
### Outputs
Effective model and diagnostic result; selected settings for subsequent requests.
### Error cases
Missing key, unreachable endpoint, or quota returns `success:false` in many cases.
### Edge cases
Switching providers must not reuse another provider's key/base URL.
### Security considerations
The browser sends optional key/base URL to backend; arbitrary base URL is an observed network risk.
### Acceptance criteria
Provider switching preserves isolation and connection test does not expose server keys.
### Related requirements
REQ-FUNC-012, REQ-SEC-003.
### Related components
`frontend/src/components/LogSummary/ModelSettingsPanel.tsx`, `frontend/src/state/selectionStore.ts`, `backend/app/services/llm/`; [analysis.md](analysis.md).

## FEATURE-008 — Log masking

### Purpose
Reduce credential and personal-data exposure before display and model processing.
### User story
As an operator, I want sensitive log text masked so investigations avoid unnecessary exposure.
### Preconditions
Backend receives log lines; optional external masking credentials may be configured.
### Workflow
Raw AWS message → external masking batch or local regex fallback → API/browser; analysis endpoint re-masks submitted messages.
### Business rules
External failures fall back locally for failed and remaining sub-batches. `/api/mask/test` exercises only the local masker.
### Inputs
Raw log text and masking settings.
### Outputs
Masked text in results, streams, cursors, and analysis prompts.
### Error cases
External timeout/4xx/5xx/malformed body falls back; regex coverage is finite.
### Edge cases
Already masked messages are passed through re-masking; private data in non-message metadata or typed prompts needs separate review.
### Security considerations
Masking is best-effort and not a guarantee of de-identification; external TLS verification defaults false.
### Acceptance criteria
No raw AWS message reaches search/stream responses in covered cases; failure tests prove fallback.
### Related requirements
REQ-SEC-001, REQ-SEC-002, REQ-REL-002.
### Related components
`backend/app/services/masking.py`, `backend/app/core/masking_http_client.py`; [security.md](security.md).
