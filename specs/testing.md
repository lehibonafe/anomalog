# Testing

## Current test inventory

Backend uses pytest/pytest-asyncio under `backend/tests/`; tests mock AWS and model SDK calls. Run `cd backend && .venv/bin/python -m pytest tests/`. Frontend uses Vitest for three utility/state test files: `src/utils/time.test.ts`, `src/utils/logFacets.test.ts`, and `src/state/selectionStore.test.ts`. Run `cd frontend && npm run test && npm run lint && npm run build`. ESLint and TypeScript/Vite are additional static/build checks. These commands are specified in `AGENTS.md` and package scripts; this specification creation did not change production code.

| Feature | Requirement | Current representative test |
| --- | --- | --- |
| FEATURE-001 | REQ-FUNC-001 | `backend/tests/test_cloudwatch_service.py` discovery and linked-account cases. |
| FEATURE-002 | REQ-FUNC-002, REQ-FUNC-004, REQ-FUNC-005 | `test_cloudwatch_service.py` pagination/masking/cursor; `frontend/src/state/selectionStore.test.ts` stale-result state. |
| FEATURE-003 | REQ-FUNC-003, REQ-FUNC-004 | `backend/tests/test_cloudtrail_service.py` modes, filters, order, pagination. |
| FEATURE-004 | REQ-FUNC-006, REQ-FUNC-007, REQ-REL-001 | `backend/tests/test_live_tail_service.py` stream/session behavior; no automated browser confirmation flow. |
| FEATURE-005 | REQ-FUNC-008, REQ-FUNC-009, REQ-FUNC-010, REQ-PERF-002 | `frontend/src/utils/logFacets.test.ts`; no exporter or full dashboard interaction test. |
| FEATURE-006 | REQ-FUNC-011, REQ-FUNC-013, REQ-REL-003 | `test_anomaly_service.py`, `test_investigator_analysis.py`, `test_log_filter.py`; no browser history flow test. |
| FEATURE-007 | REQ-FUNC-012 | `backend/tests/services/llm/test_*_provider.py`, `test_registry.py`, selection store tests; no Model settings UI test. |
| FEATURE-008 | REQ-SEC-001, REQ-SEC-002, REQ-REL-002 | `test_masking.py`, `test_masking_batch.py`, anomaly/search/Live Tail service tests. |

`backend/tests/test_aws_session.py` covers source and assumed-role sessions; `backend/tests/test_meta.py` covers CloudTrail capability reporting. Prompt tests cover v4/v5/v6 content, while runtime analysis imports v6. No checked-in browser E2E suite, live AWS/provider integration suite, load test, dependency/security scanner, CI workflow, or infrastructure test was found. These are coverage gaps, not evidence that the application fails in those environments.

## Verification policy

- Service, masking, pagination, provider, and API-contract changes: add a targeted regression test using mocks; run the backend suite and update [api.md](api.md) plus [root API reference](../api-reference.md) if needed.
- UI behavior changes: add a meaningful Vitest test where logic can be isolated, run test/lint/build, and manually inspect important browser interactions. Do not add tests that merely mirror the implementation.
- Deployment and IAM changes: validate an allowed and a denied AWS read in a controlled environment; never make live/billable AWS or model calls from automated unit tests.
- Security-sensitive changes: add negative cases for masking, credentials, cursor tampering, URL overrides, or export encoding as applicable.

**Recommended additions:** browser tests for Live Tail confirmation/stop, Model settings isolation, citation navigation, history deletion, filtered export; route-level tests for response/error envelopes and oversized input; controlled performance checks for multi-group cursor size and long Live Tail sessions. These are recommendations, not present gates.
