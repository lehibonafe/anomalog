import type { LogEvent } from "../api/types";

export type FindingSeverity = "critical" | "warning" | "info";

export interface Finding {
  id: string;
  label: string;
  regex: RegExp;
  severity: FindingSeverity;
}

// Kept in priority order (critical first) — a line's overall severity tint uses
// whichever finding here matches first. Regexes mirror backend/app/services/
// log_filter.py's INTERESTING_RE so "what the UI flags" and "what the AI
// prefilter scans" agree.
export const FINDINGS: Finding[] = [
  { id: "5xx", label: "5xx server error", regex: /\b5\d\d\b/, severity: "critical" },
  { id: "error", label: "ERROR", regex: /\bERROR\b/i, severity: "critical" },
  { id: "exception", label: "Exception / traceback", regex: /\b(EXCEPTION|TRACEBACK|PANIC)\b/i, severity: "critical" },
  { id: "fatal", label: "Fatal / critical", regex: /\b(FATAL|CRITICAL)\b/i, severity: "critical" },
  { id: "4xx", label: "4xx client error", regex: /\b4\d\d\b/, severity: "warning" },
  { id: "timeout", label: "Timeout", regex: /\btimed?[ -]?out\b/i, severity: "warning" },
  { id: "refused-denied", label: "Refused / denied", regex: /\b(refused|denied)\b/i, severity: "warning" },
  { id: "warn", label: "Warning", regex: /\bWARN\b/i, severity: "warning" },
  { id: "3xx", label: "3xx redirect", regex: /\b3\d\d\b/, severity: "info" },
];

export interface FindingCount {
  finding: Finding;
  count: number;
}

export function countFindings(events: LogEvent[]): FindingCount[] {
  return FINDINGS.map((finding) => ({
    finding,
    count: events.reduce((n, e) => (finding.regex.test(e.message) ? n + 1 : n), 0),
  }))
    .filter((c) => c.count > 0)
    .sort((a, b) => b.count - a.count);
}

/** The highest-priority finding category present in a line, or null if none match. */
export function getLineSeverity(message: string): FindingSeverity | null {
  return FINDINGS.find((f) => f.regex.test(message))?.severity ?? null;
}

export interface HighlightSegment {
  text: string;
  severity: FindingSeverity | null;
}

function groupName(id: string): string {
  return `g_${id.replace(/-/g, "_")}`;
}

const HIGHLIGHT_RE = new RegExp(
  FINDINGS.map((f) => `(?<${groupName(f.id)}>${f.regex.source})`).join("|"),
  "gi"
);
const GROUP_SEVERITY: Record<string, FindingSeverity> = Object.fromEntries(
  FINDINGS.map((f) => [groupName(f.id), f.severity])
);

/** Splits a message into plain/highlighted segments for inline severity-keyword coloring. */
export function splitHighlighted(message: string): HighlightSegment[] {
  const segments: HighlightSegment[] = [];
  let lastIndex = 0;
  for (const match of message.matchAll(HIGHLIGHT_RE)) {
    const index = match.index ?? 0;
    if (index > lastIndex) segments.push({ text: message.slice(lastIndex, index), severity: null });
    const groups = match.groups ?? {};
    const matchedGroup = Object.keys(groups).find((k) => groups[k] !== undefined);
    segments.push({ text: match[0], severity: matchedGroup ? GROUP_SEVERITY[matchedGroup] : null });
    lastIndex = index + match[0].length;
  }
  if (lastIndex < message.length) segments.push({ text: message.slice(lastIndex), severity: null });
  return segments;
}
