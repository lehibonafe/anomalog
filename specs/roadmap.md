# Roadmap and gaps

This file records possible work. **Recommendations and ideas here are not implemented behavior or approved requirements.** Promote an item to [requirements.md](requirements.md) only after product/security review.

## Current System

One React/Vite page calls a FastAPI service for CloudWatch and CloudTrail search, CloudWatch Live Tail, masking, and five LLM adapters. The UI supports facets, charts, export, citations, and local completed-chat history. Local development uses `dev.sh` or Docker Compose. Backend pytest and frontend Vitest/lint/build exist. There is no app database, end-user authentication, checked-in CI/CD, production ingress, or telemetry pipeline. See [architecture.md](architecture.md) and [testing.md](testing.md).

## Recommended Improvements

1. **Secure deployment access:** confirm the production perimeter; add an authenticated proxy or in-app identity model before broader exposure. Limit backend port reachability. See [security.md](security.md) and ASM-003.
2. **Review outbound trust:** require verified TLS for external masking once certificates permit; use HTTPS or a verified private channel for the default LiteLLM proxy; constrain or approve user-supplied provider base URLs; audit any exception text returned to clients.
3. **Harden cursor integrity and input bounds:** authenticate or server-store continuation state, and set explicit size/range limits for request arrays/text. Add negative tests for cursor tampering and oversized bodies.
4. **Resolve documentation drift:** add or remove README references to missing `update-ec2.sh`, `deploy.sh`, and `api-reference_1.md`; review stale module names in `CLAUDE.md`; check the DOCX guides against the actual deployment; define a real production build, release, rollback, and health-check path.
5. **Expand meaningful UI/API tests:** browser flows for cost confirmation, source switch, citation, export, history deletion, and model settings; route error-envelope and security regression tests. Keep automated AWS/model calls mocked.
6. **Add operational telemetry:** request latency/error metrics, AWS/provider dependency failure counters, Live Tail session/queue signals, and redacted structured logging; set SLOs only after workload review.
7. **Align shared API types:** review `frontend/src/api/types.ts` against Pydantic/OpenAPI after route changes; its analysis response type currently omits the backend `references` field, although the UI does not consume that field.

## Possible Future Features

- End-user authentication and roles, after defining users, resource boundaries, session lifecycle, and audit needs.
- Server-side shared investigation history, if collaboration or cross-device use is a confirmed product goal; this would introduce a database and retention policy.
- Saved searches or incident workspaces, if operators need repeatable investigations.
- Alerting or scheduled detection, if live monitoring beyond an interactive page is desired.

These are plausible extensions, not claims about current functionality or commitments. Product owners should review [product.md](product.md) and [assumptions.md](assumptions.md) before prioritizing them.
