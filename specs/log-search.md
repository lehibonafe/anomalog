# Log search and pagination

## Required behavior

- CloudWatch search accepts a list of group names or ARNs, a start and end timestamp, an optional AWS filter pattern, a requested page limit, and an opaque cursor. It returns masked events ordered by timestamp and a continuation cursor when AWS has more results.
- Log group discovery supports a keyword and AWS continuation token. Linked-account discovery includes group identifiers and account IDs when configured.
- CloudTrail search uses centralized CloudWatch log groups when configured or linked-account discovery is enabled. Otherwise it uses regional CloudTrail `LookupEvents`. Account filtering requires centralized groups.
- Regional CloudTrail event history remains in the API's newest-first order across continuation pages; centralized CloudWatch searches remain oldest-first.
- CloudTrail attributes remain optional. Search results expose the CloudTrail event name, origin, timestamp, and masked message.
- The backend enforces its configured maximum time range and caps each response at `MAX_LOG_SEARCH_LINES`; invalid requests produce a clear client error.
- Pagination must not silently discard events. Events from all selected groups remain in timestamp order across page boundaries. The frontend sends each returned cursor for the next page, appends the response, and keeps line indices unique for citations and navigation.
- Buffered cursor events are masked before encoding and masked again when a cursor is accepted.
- A response from an older search or page must not replace or append to a newer search, a different source, or an active Live Tail session.
- Switching sources clears loaded rows and invalidates any pending search response from the previous source.
- The CloudTrail account selector reflects whether the backend can filter centralized groups; regional event history does not offer account selection.

## Acceptance checks

- Service tests mock AWS, cover both CloudTrail modes, masking, cursor continuation, and page boundaries.
- Search from the UI retains active filters when a new page is appended.
- Interleaved timestamps from multiple groups stay ordered across page boundaries, and late responses from previous searches are ignored.
