# Product

## Verified product behavior

Anomalog presents one browser workspace for CloudWatch log-group discovery and historical search, CloudTrail search, CloudWatch Live Tail, log filtering and analytics, export, and AI investigation of currently visible lines. The backend reads AWS data, masks log messages, and sends selected evidence to an LLM provider. The implementation and overview are in `frontend/src/App.tsx`, `backend/app/main.py`, and [root README](../README.md).

The UI is a single page with CloudWatch and CloudTrail source tabs; there is no application user account, registration, or administrative UI. Supported analysis adapters are LiteLLM, Gemini, OpenAI, Anthropic, and Ollama (`backend/app/services/llm/registry.py`).

## Inferred intent

The wording “AI Log Investigator,” cited line navigation, account labels, and operational questions suggest the primary users are operators, SREs, and incident investigators. This is **inferred**, not a verified customer or organizational requirement; see [ASM-001](assumptions.md#asm-001).

| Persona (inferred) | Goal | Evidence |
| --- | --- | --- |
| Incident investigator | Find failures and supporting log lines quickly | Suggested questions and citations in `frontend/src/components/LogSummary/`. |
| Cloud operator | Examine selected AWS groups and CloudTrail activity | Source pickers and time filters in `frontend/src/components/`. |
| Deployment maintainer | Configure AWS access, masking, model provider, and network access | `backend/app/config.py`, `docker-compose.yml`, README. |

## Goals and boundaries

| Product goal | Current supporting features | Success criterion derived from code/specs |
| --- | --- | --- |
| **PG-001** Explore AWS events | FEATURE-001, FEATURE-002, FEATURE-003, FEATURE-005 | A selected, bounded query returns navigable masked events without losing continuation. |
| **PG-002** Investigate with evidence | FEATURE-006, FEATURE-007 | Answers use the visible slice and expose evidence coverage and line references. |
| **PG-003** Observe active incidents with controlled cost | FEATURE-004 | Session starts after confirmation and terminates on stop, disconnect, or inactivity. |
| **PG-004** Reduce data exposure | FEATURE-008 | Log text is masked before UI delivery and re-masked before model calls. |

Primary use cases are historical troubleshooting, CloudTrail activity review, live incident monitoring, filtered export, and question-driven summary. The current product does **not** implement application authentication, durable server-side investigation storage, log ingestion, database-backed analytics, alerting, or management of AWS observability links. These are boundaries observed in the repository, not permanent exclusions.

Business outcomes, user volume, compliance obligations, and formal success metrics are **not specified** in this checkout. Any targets for those belong to product owner confirmation before becoming requirements; see [assumptions.md](assumptions.md) and [roadmap.md](roadmap.md).
