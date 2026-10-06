# CloudWatch Live Tail

## Required behavior

- A user explicitly confirms the AWS cost before the browser sends a start message. A session accepts 1 to 10 log groups and an optional filter pattern.
- The backend owns the AWS stream and masks messages before forwarding them. Browser disconnect, stop, AWS termination, or inactivity closes the stream.
- Sessions are limited per backend process by `LIVE_TAIL_MAX_CONCURRENT_SESSIONS`. The inactivity timeout is configurable from 15 to 30 minutes. Origin validation follows `CORS_ORIGINS`.
- If the browser cannot consume messages fast enough, the backend stops the stream instead of allowing an unbounded queue.
- Pausing retains up to 5,000 events in the browser while the AWS session stays active. The UI reports dropped buffered events and estimates cost from started minutes.
- Active Live Tail retains a bounded browser history, gives every event a unique increasing line index, and reports events evicted from that history.
- Starting Live Tail waits until pending log searches finish; switching sources closes its stream without appending paused events to the new source.

## Acceptance checks

- Tests mock the AWS event stream and cover masking, stream closure, session limits, and the message protocol. No test opens a billable stream.
- Starting, pausing, resuming, and stopping leave the viewer and session status consistent.
- A multi-event update has unique line indices, and long sessions do not grow the retained event array without bound.
