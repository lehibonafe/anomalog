# Anomalog specifications

Anomalog is a browser workspace for exploring AWS CloudWatch Logs and CloudTrail events, streaming CloudWatch Live Tail, and asking an LLM questions about the visible log slice. The browser calls a FastAPI service; that service owns AWS access, masking, and provider calls. See [product.md](product.md) for verified behavior and inferred intent.

This directory is the long-term source of truth for intended application behavior. **Specifications describe the intended behavior of the system. Code implements the specifications. When intentional behavior changes, update the specification before or together with the implementation.** Existing code is evidence for the initial baseline, not proof that every behavior is safe or complete. Keep observed gaps and recommendations distinct from requirements. Record uncertain conclusions in [assumptions.md](assumptions.md).

## Index and authority

| Decision or question | Authoritative document |
| --- | --- |
| Product goals and boundaries | [product.md](product.md) |
| Stable requirement IDs and acceptance criteria | [requirements.md](requirements.md) |
| Feature IDs and behavior | [features.md](features.md), then the relevant feature detail below |
| Component ownership and data movement | [architecture.md](architecture.md), [system-design.md](system-design.md) |
| Wire contract | [api.md](api.md), with [root API reference](../api-reference.md) and generated `/openapi.json` for exact executable shapes |
| Data types and lifetime | [data-model.md](data-model.md) |
| Frontend and backend organization | [frontend.md](frontend.md), [backend.md](backend.md) |
| Security and identity | [security.md](security.md), [authentication.md](authentication.md), [iam_setup.md](iam_setup.md) |
| Runtime setup and operations | [configuration.md](configuration.md), [infrastructure.md](infrastructure.md), [deployment.md](deployment.md), [observability.md](observability.md), [error-handling.md](error-handling.md), [reliability.md](reliability.md) |
| Quality gates | [testing.md](testing.md), [performance.md](performance.md), [coding-standards.md](coding-standards.md), [development-workflow.md](development-workflow.md) |
| Uncertainty and possible work | [assumptions.md](assumptions.md), [roadmap.md](roadmap.md) |

Feature detail: [log-search.md](log-search.md), [live-tail.md](live-tail.md), [log-exploration.md](log-exploration.md), and [analysis.md](analysis.md). User journeys: [user-flows.md](user-flows.md). The separate masking service's API is documented in [its root reference](../api-reference-pii-masking.md); those routes are not implemented by Anomalog.

## How to use these specifications

1. Find the product goal, feature ID, and requirement IDs before changing behavior. Use the traceability table in [requirements.md](requirements.md).
2. Read the relevant feature spec, API/data contract, and affected frontend or backend design. Treat a conflict with implementation as a finding to resolve, not permission to silently change the spec.
3. Update intended behavior and acceptance criteria before or with code; add or update requirement IDs only when the obligation changes. Keep IDs stable and do not reuse retired IDs.
4. Update [api.md](api.md) and [root API reference](../api-reference.md) for route/schema changes. Update security, configuration, deployment, and operational specs when their contracts change.
5. Add focused tests, run the applicable checks in [testing.md](testing.md), and record material decisions and residual uncertainty in the change review. Follow [development-workflow.md](development-workflow.md).

## Specification Status

“Complete” means a repository-grounded baseline exists, not that production behavior has been independently verified. Confidence reflects visibility in this checkout.

| Area | Status | Confidence | Notes |
| --- | --- | --- | --- |
| Product | Complete | Medium | User roles and business goals are inferred from UI and README. |
| Requirements | Complete | High | IDs cover implemented major capabilities; future policy decisions remain open. |
| Architecture | Complete | High | Runtime source and Compose files are present. |
| API | Complete | High | All eight HTTP routes and one WebSocket route mapped to source. |
| Data Model | Complete | High | No application database found; API and browser state are documented. |
| Security | Complete | Medium | Code shows controls and risks; deployment perimeter is outside repo. |
| Infrastructure | Complete | Medium | Compose is present; production proxy and EC2 setup are not checked in. |
| Testing | Complete | High | Test inventory is visible; no live integration or browser E2E evidence. |
| Deployment | Complete | Low | README names scripts absent from this checkout. |
| Observability | Complete | Medium | Health and log calls visible; external monitoring is unknown. |
