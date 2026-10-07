# Roadmap and gaps

This file records possible work. **Recommendations and ideas here are not implemented behavior or approved requirements.** Promote an item to [requirements.md](requirements.md) only after product/security review.

## Current System

One React/Vite page calls a FastAPI service for CloudWatch and CloudTrail search, CloudWatch Live Tail, masking, and five LLM adapters. The UI supports facets, charts, export, citations, and local completed-chat history. Local development uses `dev.sh` or Docker Compose; `deploy.sh` builds a local-only production stack for same-host or same-network callers. Backend pytest and frontend Vitest/lint/build exist. There is no app database, end-user authentication, checked-in CI/CD, host production ingress, or telemetry pipeline. See [architecture.md](architecture.md) and [testing.md](testing.md).

## Recommended Improvements

1. **Secure deployment access:** confirm the production perimeter and key handling; add a browser sign-in flow if the React UI must work with the protected production API. Keep backend port reachability limited and require TLS before remote access. See [security.md](security.md) and ASM-003.
2. **Review outbound trust:** require verified TLS for external masking once certificates permit; use HTTPS or a verified private channel for the default LiteLLM proxy; review approved provider base URLs and audit any exception text returned to clients.
3. **Harden cursor integrity and input bounds:** authenticate or server-store continuation state, and set explicit size/range limits for request arrays/text. Add negative tests for cursor tampering and oversized bodies.
4. **Complete release operations:** add CI/CD and a tested rollback procedure; if remote access becomes necessary, define and validate HTTPS ingress and caller authorization. Review stale module names in `CLAUDE.md` and check the DOCX guides against the actual deployment.
5. **Expand meaningful UI/API tests:** browser flows for cost confirmation, source switch, citation, export, history deletion, and model settings; route error-envelope and security regression tests. Keep automated AWS/model calls mocked.
6. **Add operational telemetry:** request latency/error metrics, AWS/provider dependency failure counters, Live Tail session/queue signals, and redacted structured logging; set SLOs only after workload review.
7. **Align shared API types:** review `frontend/src/api/types.ts` against Pydantic/OpenAPI after route changes; its analysis response type currently omits the backend `references` field, although the UI does not consume that field.

## Possible Future Features

- End-user authentication and roles, after defining users, resource boundaries, session lifecycle, and audit needs.
- Server-side shared investigation history, if collaboration or cross-device use is a confirmed product goal; this would introduce a database and retention policy.
- Saved searches or incident workspaces, if operators need repeatable investigations.
- Alerting or scheduled detection, if live monitoring beyond an interactive page is desired.

These are plausible extensions, not claims about current functionality or commitments. Product owners should review [product.md](product.md) and [assumptions.md](assumptions.md) before prioritizing them.
