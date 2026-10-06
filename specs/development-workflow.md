# Spec-driven development workflow

```text
Idea
 ↓
Specification
 ↓
Requirements
 ↓
Acceptance Criteria
 ↓
Implementation Plan
 ↓
Code
 ↓
Tests
 ↓
Validation
 ↓
Specification Update
```

For every feature or intentional behavior change:

1. Create or update the relevant section of [features.md](features.md) and its focused feature spec.
2. Assign or link stable IDs in [requirements.md](requirements.md); do not turn an unconfirmed assumption into a requirement.
3. Define observable acceptance criteria, including error and security cases.
4. Identify affected browser, backend, API, AWS/provider, and deployment components using [architecture.md](architecture.md).
5. Write a small implementation plan and note compatibility or migration concerns.
6. Implement the smallest required change, following [coding-standards.md](coding-standards.md).
7. Add or update meaningful tests; keep AWS and model calls mocked in automated tests.
8. Run affected test/lint/build checks, review acceptance criteria, and record remaining gaps.
9. Reconcile specification text, [api.md](api.md), [root API reference](../api-reference.md), configuration examples, and implementation if the final behavior differs from the plan.
10. Record significant architecture/security decisions and rationale in the change review; create an ADR if the team adopts that practice.

Agents should **not** implement large behavioral changes that contradict these specifications without updating the appropriate specification. If code and spec disagree, identify whether the code is a bug, the spec is stale, or the change is intentional before editing. Do not silently promote a recommendation from [roadmap.md](roadmap.md) into a current requirement. Keep IDs stable; add new IDs instead of reusing old ones.
