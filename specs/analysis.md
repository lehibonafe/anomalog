# AI investigation

## Required behavior

- Analysis accepts only the events submitted in the request, with a source description, provider choice, optional model settings, question, and conversation history.
- The backend masks request messages again before any provider call, including requests that bypass search routes.
- Retrieval selects relevant events, compacts repetitive lines, caps lines, characters, and estimated tokens, and chunks provider calls according to server settings.
- Responses report model, analyzed/omitted line and chunk counts, estimated input tokens, and warnings for limits or partial provider failures. A failed consolidation can fall back to the available batch answers.
- Connection testing returns a success flag and message as a normal response; it does not expose provider credentials.
- The UI keeps keys, models, and base URLs separate for each provider and identifies the destination used for a connection test or analysis.

## Acceptance checks

- Provider and service tests mock SDK calls. Tests cover masking, retrieval limits, partial failures, and response accounting without live LLM traffic.
- Changing providers cannot reuse another provider's API key or custom base URL.
