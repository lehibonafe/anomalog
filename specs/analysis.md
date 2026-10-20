# AI investigation

## Required behavior

- Analysis accepts only the events submitted in the request, with a source description, provider choice, optional model settings, question, and conversation history.
- The backend masks request messages again before any provider call, including requests that bypass search routes.
- Retrieval selects relevant events, compacts repetitive lines, caps lines, characters, and estimated tokens, and chunks provider calls according to server settings.
- Responses report model, analyzed/omitted line and chunk counts, estimated input tokens, and warnings for limits or partial provider failures. A failed consolidation can fall back to the available batch answers.
- Connection testing returns a success flag and message as a normal response; it does not expose provider credentials.
- Optional model base URLs must exactly match the provider default or an additional server-approved URL for that provider before the provider client is created.
- The UI keeps keys, models, and base URLs separate for each provider and identifies the destination used for a connection test or analysis.
- Completed investigations are stored in one backend SQLite history shared by all callers. New browsers can list and delete entries without a user account; existing browser history is imported once. Questions and answers are masked again before persistence, and original log events and provider keys are not stored.

## Acceptance checks

- Provider and service tests mock SDK calls. Tests cover masking, retrieval limits, partial failures, and response accounting without live LLM traffic.
- Changing providers cannot reuse another provider's API key or custom base URL.
- Unapproved model destinations fail before any SDK call; approved destinations reach the selected provider only.
- A saved conversation appears on another browser after refreshing history. A failed save is visible and retryable. History survives backend container recreation when the SQLite directory is mounted on a persistent volume.
