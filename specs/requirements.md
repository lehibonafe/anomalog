# Requirements and traceability

IDs are stable. Each row is an intended obligation based on the current feature set; the evidence column distinguishes implementation or test evidence from checks still needed. REQ-SEC-005 is a deployment boundary that cannot be verified from this checkout. Priority is an engineering assessment, not a business commitment. Acceptance checks use mocks unless explicitly approved deployment validation is required.

| ID | Category | Requirement | Priority | Evidence / acceptance criteria |
| --- | --- | --- | --- | --- |
| REQ-FUNC-001 | Functional | Discover CloudWatch groups with keyword, owner metadata when available, and continuation. | High | `cloudwatch_service.list_log_groups`; paged picker; `test_cloudwatch_service.py`. |
| REQ-FUNC-002 | Functional | Search selected CloudWatch groups within a bounded time range and optional AWS pattern. | High | Search route returns masked events and cursor; reject range above configured maximum. |
| REQ-FUNC-003 | Functional | Search CloudTrail through configured/linked log groups or regional event history. | High | Both modes and account-filter constraints covered by `test_cloudtrail_service.py`. |
| REQ-FUNC-004 | Functional | Preserve selected query and event order across continuation pages without dropping rows. | High | Cursor tests cover interleaved groups, empty pages, invalid reuse, regional newest-first pages. |
| REQ-FUNC-005 | Functional | Invalidate stale search responses when a new search, source change, or Live Tail session begins. | High | `selectionStore.ts` generation checks; `selectionStore.test.ts`. |
| REQ-FUNC-006 | Functional | Require cost confirmation and 1–10 groups before starting CloudWatch Live Tail. | High | Confirmation UI and start-message validation; mocked stream test. |
| REQ-FUNC-007 | Functional | Allow Live Tail pause/resume/stop while reporting dropped events, sampling, time, and estimated cost. | High | `LiveTailControls.tsx`; 5,000 paused buffer and 10,000 displayed history caps. |
| REQ-FUNC-008 | Functional | Filter loaded logs by keyword, facets, and findings; expose only visible rows to analysis and export. | High | `LogViewer.tsx` passes `filteredEvents` to `App.tsx`; viewer acceptance checks. |
| REQ-FUNC-009 | Functional | Provide log analytics, timestamp chart, significant HTTP-status counts, and citation navigation. | Medium | Dashboard, chart, facet utilities, `AnalysisResult.tsx`. |
| REQ-FUNC-010 | Functional | Export visible rows as JSON, CSV, or text. | Medium | `LogViewer.tsx` serialization and download. |
| REQ-FUNC-011 | Functional | Analyze submitted evidence with provider selection, follow-up history, coverage counts, and partial-result warnings. | High | `AnomalyService.analyze`; `test_anomaly_service.py`, `test_investigator_analysis.py`. |
| REQ-FUNC-012 | Functional | Keep model settings separate by provider and offer a connection diagnostic. | Medium | Selection store, Model settings panel, test-connection route. |
| REQ-FUNC-013 | Functional | Save bounded completed investigation history in browser local storage and allow deletion. | Medium | `LogSummary.tsx`; max 20 saved conversations. |
| REQ-SEC-001 | Security | Mask AWS log text before returning it to the browser, with local fallback if external masking fails. | Critical | Masking service tests and search/stream service tests. |
| REQ-SEC-002 | Security | Re-mask client-submitted events before sending them to an LLM. | Critical | `AnomalyService.analyze`; masking tests. |
| REQ-SEC-003 | Security | Keep server credentials out of `/api/config` and browser AWS access. | Critical | Meta route returns flags; AWS calls live in backend. |
| REQ-SEC-004 | Security | Escape spreadsheet formula prefixes in CSV export. | Medium | `LogViewer.tsx` `csvCell`; add focused test when exporter changes. |
| REQ-SEC-005 | Security/Operational | Restrict deployed API access at a network or authenticated-proxy boundary until app authentication exists. | Critical | No auth middleware in `main.py`; deployment validation must check perimeter. |
| REQ-PERF-001 | Performance | Bound search response size, analysis input, Live Tail buffers, and provider input with configured limits. | High | Settings, service caps, bounded WebSocket queue, browser buffers. |
| REQ-PERF-002 | Performance | Virtualize visible rows and avoid facet parsing for keyword-only filtering. | Medium | `LogViewer.tsx` and facet cache; frontend tests. |
| REQ-REL-001 | Reliability | Close Live Tail on stop, disconnect, inactivity, AWS end, or slow consumer. | High | WebSocket route and stream tests. |
| REQ-REL-002 | Reliability | Continue with local masking when the external masker fails. | High | `mask_messages_batch`; batch failure tests. |
| REQ-REL-003 | Reliability | Return usable partial batch answers when later LLM calls fail, with warnings. | Medium | `AnomalyService`; partial-failure tests. |
| REQ-OPS-001 | Operational | Expose health and safe capability configuration endpoints. | Medium | `routes_meta.py`; health is a shallow process check. |
| REQ-OPS-002 | Operational | Use environment-backed settings and optional monitoring-account role assumption. | High | `config.py`, `aws_session.py`, Compose, AWS session tests. |
| REQ-OPS-003 | Operational | Verify changes with mocked backend tests and frontend test/lint/build; sync API docs for contract changes. | High | `AGENTS.md`; [testing.md](testing.md). |

**Compliance:** Not currently applicable as a specified requirement. The repo has privacy controls, but no named regulation, retention policy, or audit obligation. See [ASM-002](assumptions.md#asm-002).

## Traceability: goal → feature → requirement → component → implementation → test

| Goal | Feature | Requirements | Component and implementation | Representative test |
| --- | --- | --- | --- | --- |
| PG-001 | FEATURE-001 | REQ-FUNC-001, REQ-OPS-002 | CloudWatch API/service, `backend/app/services/cloudwatch_service.py`; picker | `backend/tests/test_cloudwatch_service.py` |
| PG-001 | FEATURE-002 | REQ-FUNC-002, REQ-FUNC-004, REQ-FUNC-005, REQ-PERF-001 | Search service, `group_pagination.py`, `useCloudWatchSearch.ts` | `test_cloudwatch_service.py`, `selectionStore.test.ts` |
| PG-001 | FEATURE-003 | REQ-FUNC-003, REQ-FUNC-004, REQ-FUNC-005 | `cloudtrail_service.py`, `useCloudTrailSearch.ts` | `test_cloudtrail_service.py` |
| PG-003 | FEATURE-004 | REQ-FUNC-006, REQ-FUNC-007, REQ-REL-001 | `routes_cloudwatch.py`, `live_tail_service.py`, `LiveTailControls.tsx` | `test_live_tail_service.py`; browser flow gap |
| PG-001 | FEATURE-005 | REQ-FUNC-008, REQ-FUNC-009, REQ-FUNC-010, REQ-PERF-002, REQ-SEC-004 | `LogViewer/`, `utils/logFacets.ts` | `logFacets.test.ts`; export/browser gap |
| PG-002 | FEATURE-006 | REQ-FUNC-011, REQ-FUNC-013, REQ-REL-003 | `anomaly_service.py`, `LogSummary.tsx` | `test_anomaly_service.py`; history UI gap |
| PG-002 | FEATURE-007 | REQ-FUNC-012, REQ-SEC-003 | LLM registry/providers, Model settings UI | provider tests; UI interaction gap |
| PG-004 | FEATURE-008 | REQ-SEC-001, REQ-SEC-002, REQ-REL-002 | `masking.py`, `masking_http_client.py` | `test_masking.py`, `test_masking_batch.py` |

Cross-cutting REQ-SEC-005, REQ-OPS-001, and REQ-OPS-003 apply to every deployed feature. Detailed feature acceptance criteria are in [features.md](features.md) and the four focused feature specs.
