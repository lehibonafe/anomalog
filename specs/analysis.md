# AI investigation

## Required behavior

- Analysis accepts only the events submitted in the request, with a source description, provider choice, optional model settings, question, and conversation history.
- The backend masks request messages again before any provider call, including requests that bypass search routes.
- Retrieval selects relevant events, compacts repetitive lines, caps lines, characters, and estimated tokens, and chunks provider calls according to server settings.
- Responses report model, analyzed/omitted line and chunk counts, estimated input tokens, and warnings for limits or partial provider failures. A failed consolidation can fall back to the available batch answers.
- If the selected provider fails after its configured retries, analysis retries that chunk with the server-configured Gemini provider when `GEMINI_API_KEY` is set. The response warns when failover occurs and reports the Gemini model when any chunk used it.
- Connection testing returns a success flag and message as a normal response; it does not expose provider credentials.
- Optional model base URLs must exactly match the provider default or an additional server-approved URL for that provider before the provider client is created.
- An HTTPS LiteLLM proxy signed by a private CA may use an operator-provided CA PEM. The LiteLLM client adds that CA to its trusted roots while continuing to verify the certificate and hostname by default. An explicit `LITELLM_VERIFY_SSL=false` operator setting disables both checks for LiteLLM only; other provider clients keep their own trust settings.
- The UI keeps keys, models, and base URLs separate for each provider and identifies the destination used for a connection test or analysis.
- Completed investigations are stored in one backend SQLite history shared by all callers. New browsers can list and delete entries without a user account; existing browser history is imported once. Questions and answers are masked again before persistence, and original log events and provider keys are not stored.

## Acceptance checks

- Provider and service tests mock SDK calls. Tests cover masking, retrieval limits, partial failures, and response accounting without live LLM traffic.
- Changing providers cannot reuse another provider's API key or custom base URL.
- Unapproved model destinations fail before any SDK call; approved destinations reach the selected provider only.
- A configured LiteLLM CA file is loaded into the LiteLLM HTTPS client; an absent file fails startup configuration clearly, while malformed PEM returns a safe provider-configuration error on analysis or `success:false` on connection test. No test sends a live model request.
- With `LITELLM_VERIFY_SSL=false`, the LiteLLM client is constructed with verification disabled and skips CA loading. With the default setting, no insecure LiteLLM client is constructed.
- A saved conversation appears on another browser after refreshing history. A failed save is visible and retryable. History survives backend container recreation when the SQLite directory is mounted on a persistent volume.
