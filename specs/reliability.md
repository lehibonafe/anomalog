# Reliability

## Existing mechanisms

Search pages are bounded and resumable with opaque cursors; selected CloudWatch groups are merged without dropping buffered events. The browser ignores stale search responses. External masking failure falls back to local regex masking; model chunk failures can yield partial answers and warnings. Provider SDK calls have a bounded timeout and app-managed retry for rate-limit signals. Live Tail closes on stop, disconnect, inactivity, AWS termination, or slow consumer and uses a bounded queue. Evidence: `group_pagination.py`, `selectionStore.ts`, `masking.py`, `anomaly_service.py`, `routes_cloudwatch.py`.

The system has single points of failure: one FastAPI process/container for a local Compose deployment, one configured AWS region/identity, the browser's in-memory loaded data, and the chosen model endpoint for each analysis. Per-process limiters do not coordinate multiple workers. No persistent server queue, failover, autoscaling, backup, disaster-recovery automation, or application availability target is checked in. Database backup is **Not currently applicable** because no application database exists; browser local-storage history and AWS logs have separate retention outside app control.

## Failure and recovery matrix

| Failure | Current response | Operator recovery |
| --- | --- | --- |
| AWS credentials/IAM/region error | Search/discovery may fail; health can still return 200 | Verify backend identity, region, role trust, and allowed group; see [iam_setup.md](iam_setup.md). |
| Masking service unavailable | Local regex fallback; warning log | Restore masking service or keep local-only mode after privacy review. |
| Provider quota/outage | Retry rate limits; partial or failed analysis | Retry later, narrow evidence, or select another configured provider. |
| Browser disconnect during Live Tail | Backend closes stream | Start a new confirmed session; lost browser-only events are not recovered. |
| Backend restart | In-flight requests/streams end; per-process state resets | Reload UI and rerun searches; continuation cursor compatibility across versions is not guaranteed. |
| Browser storage cleared | Saved investigation history disappears | No server recovery path exists. |

## Proposed reliability measures

No SLO or error budget is defined. **Recommendations:** measure API availability, valid search success, model answer completion, unexpected stream termination, and time to recover from a failed deployment. Set target values only after learning expected usage and external dependency behavior. A future readiness check could separately test AWS/model/masking dependencies without causing billable calls. Do not treat the current `/api/health` as readiness. See [observability.md](observability.md).
