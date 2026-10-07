# Assumptions and unknowns

The conclusions below are uncertain from this checkout. They are **not** current requirements.

## ASM-001

**Assumption:** Operators, SREs, and incident investigators are the main users.

**Reason:** UI vocabulary and suggested questions target operational investigations.

**Evidence:** `frontend/src/components/LogSummary/LogSummary.tsx`, `README.md`.

**Impact if incorrect:** Product priorities, terminology, and accessibility review may need revision.

**Needs confirmation:** Yes.

## ASM-002

**Assumption:** No named compliance framework or contractual retention period currently governs Anomalog.

**Reason:** None is specified in code, tests, or checked-in Markdown; masking exists but does not establish a legal obligation.

**Evidence:** `specs/`, `backend/app/services/masking.py`, repository inventory.

**Impact if incorrect:** Data retention, audit, encryption, provider selection, and history storage requirements could change materially.

**Needs confirmation:** Yes.

## ASM-003

**Assumption:** Only trusted processes on the EC2 host and trusted containers attached to the production Compose network can reach the API.

**Reason:** `deploy.sh` and production Compose bind only a loopback frontend port and do not publish the backend port. Containers attached to the Compose network can still reach the backend directly.

**Evidence:** `README.md`, `docker-compose.prod.yml`, `deploy.sh`; actual host processes, Docker network membership, and any separate ingress remain unverified.

**Impact if incorrect:** Untrusted local processes, connected containers, or an external ingress could attempt access to the protected API. A stolen or shared machine key would permit billable streaming/model operations within the backend's AWS permissions.

**Needs confirmation:** Yes.

## ASM-004

**Assumption:** External AWS observability links and centralized CloudTrail delivery are provisioned outside this repository when enabled.

**Reason:** Code reads configured or linked groups but contains no setup API or IaC for OAM/log centralization.

**Evidence:** `backend/app/services/cloudtrail_service.py`, `cloudwatch_service.py`, `backend/app/config.py`.

**Impact if incorrect:** Linked-account searches may fail or omit intended accounts.

**Needs confirmation:** Yes.

## ASM-005

**Assumption:** The DOCX operational guides may describe an environment beyond this checkout and may be stale.

**Reason:** They contain deployment/operations sections, while some scripts named by README are absent. No automated synchronization exists.

**Evidence:** Two root `.docx` files, `README.md`, file inventory.

**Impact if incorrect:** Operational steps could be duplicated or contradict this specification set.

**Needs confirmation:** Yes.

## ASM-006

**Assumption:** Expected concurrency, request volume, latency, and availability targets have not been formally set.

**Reason:** Limits exist in code, but no workload model, SLO, or load test is checked in.

**Evidence:** `backend/app/config.py`, `backend/app/core/rate_limiter.py`, no metrics/CI configuration.

**Impact if incorrect:** Performance and reliability recommendations may be under- or over-scoped.

**Needs confirmation:** Yes.
