# Anomalog specifications

These files describe observable behavior and constraints for changes to Anomalog. Read the relevant spec before editing a route, service, or UI feature; update it when behavior changes. Keep implementation notes and verification evidence in the pull request, not in the behavior spec.

| Area | Specification |
| --- | --- |
| Log search and pagination | [log-search.md](log-search.md) |
| Live streaming | [live-tail.md](live-tail.md) |
| Viewer and analytics | [log-exploration.md](log-exploration.md) |
| AI investigation | [analysis.md](analysis.md) |
| Performance and resource use | [performance.md](performance.md) |

The wire contract is documented separately in [api-reference.md](../api-reference.md). Backend Pydantic models and route declarations are the source of truth for executable validation and OpenAPI at `/openapi.json`; update the reference whenever those contracts change.

For each change: state the behavior in its spec, implement it, add regression coverage where a service or contract changes, and run the affected checks. The normal gates are `cd backend && .venv/bin/python -m pytest tests/` and `cd frontend && npm run test && npm run lint && npm run build`.
