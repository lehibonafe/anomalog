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

**Assumption:** Production access is restricted by infrastructure outside this repository.

**Reason:** README describes an HTTPS reverse proxy/network restriction, but no proxy, firewall, or named deployment scripts are checked in.

**Evidence:** `README.md`, `docker-compose.yml`, absent `update-ec2.sh` and `deploy.sh` in tracked inventory.

**Impact if incorrect:** Unauthenticated API and billable streaming/model operations may be publicly reachable.

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
