# Log exploration

## Required behavior

- The log viewer supports keyword, facet, and finding filters. The visible subset is the exact subset offered to the AI investigator and export controls.
- Facets are derived from structured log fields first, then recognizable text. HTTP status cards count only the documented significant codes. A status contributes to at most one HTTP family.
- The chart, facet counts, and status overview update when logs arrive or pagination appends more events. Selected filters continue to work across appended pages.
- The viewer virtualizes rows and supports expanding JSON, keyboard navigation, line highlighting, and JSON/CSV/text export. CSV values that could become spreadsheet formulas are escaped.
- A cited line can scroll the viewer to its corresponding loaded event.

## Acceptance checks

- Facet extraction tests cover structured fields, HTTP response text, unrelated numbers, and the significant-code set.
- Filtering with no facet selected must not parse every message solely to decide whether it matches. Repeated reads of an unchanged event should reuse extracted facets; changing its message must refresh them.
