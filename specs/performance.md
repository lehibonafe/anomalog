# Performance and resource use

## Existing implementation and limits

Expected production workload, user count, throughput, and latency targets are unknown ([ASM-006](assumptions.md#asm-006)). The code has explicit bounds: `MAX_TIME_RANGE_DAYS` defaults to 7; `MAX_LOG_SEARCH_LINES` defaults to 5,000 per response; analysis line/character/token/history/chunk settings live in `backend/app/config.py`; Live Tail permits 1–10 groups, uses a 50-message server queue, a per-process session cap of 3 by default, a 5,000-event browser pause buffer, and a 10,000-event displayed-history cap. Regional CloudTrail `LookupEvents` pages are at most 50. Searches use AWS pagination and cursors rather than loading all data at once.

`LogViewer.tsx` uses `react-window` virtualization. Keyword-only filtering skips facet parsing; `utils/logFacets.ts` caches extracted facets for unchanged events. The dashboard and chart derive counts from loaded browser events. The backend's `group_pagination.py` may buffer masked events from several groups inside a compressed cursor, with an 8 MB decompressed cursor cap; many groups or large messages can increase cursor size and serialization cost.

There is no database query/index or connection-pool consideration because no app database exists. `get_settings`, AWS sessions, masker client, and anomaly service are cached per process. Per-process HTTP/provider rate limits and Live Tail caps scale independently with worker count; they are not cluster-wide controls.

## Potential bottlenecks and recommendations

| Area | Observed basis | Recommendation, not implemented |
| --- | --- | --- |
| Multi-group search | Sequential AWS page reads and merge state in `group_pagination.py` | Measure latency/cursor size with realistic group counts before changing algorithm. |
| Masking | External HTTP sub-batches can wait for timeout before fallback | Track fallback rate and latency; validate batch size and transport. |
| AI analysis | Retrieval, prompt chunking, provider pacing, and up to 180-second SDK timeout | Measure end-to-end and per-provider latency; design partial-progress UX only if needed. |
| Browser filtering/dashboard | Arrays recalculate when events or filters change | Profile large loaded sets; retain virtualization and facet cache. |
| Live Tail | Thread and bounded queue per session | Monitor active sessions and overflow before raising process limits. |
| Static delivery | Compose runs Vite dev server | Define a production static-asset serving path before performance claims about deployment. |

## Verification

Run `cd frontend && npm run test && npm run lint && npm run build` for UI changes and `cd backend && .venv/bin/python -m pytest tests/` after search, masking, streaming, or analysis changes. Compare the production bundle with a baseline for asset/dependency changes. Measure a concrete bottleneck before introducing architectural changes; no checked-in load test or performance budget currently exists.
