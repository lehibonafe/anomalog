# Performance and resource use

## Targets

- Keep the hot path for typing a keyword proportional to the loaded rows and the keyword comparison. Skip JSON/facet parsing when no facet filter is active, and avoid repeating parsing of an unchanged event for dashboard and chart reads.
- Keep visible row rendering bounded through virtualization. Do not render the entire loaded log set as DOM rows.
- Keep client bundles free of unused starter assets and dependencies used only for operations available through the platform. Retain dependencies that supply behavior the app actually uses.
- Keep external AWS reads paginated and bounded by server limits. Preserve masking and result ordering during optimizations.

## Verification

- Run frontend unit tests, lint, and build, and compare the production bundle with a baseline for dependency or asset changes.
- Run the backend suite after changes to log search, streaming, masking, or analysis. Measure a suspected bottleneck before introducing a larger architectural change.
