import { useMemo } from "react";

import type { LogEvent } from "../../api/types";

export type FindingSeverity = "critical" | "warning" | "info";

export interface Finding {
  id: string;
  label: string;
  regex: RegExp;
  severity: FindingSeverity;
}

// Kept in rough priority order; regexes mirror backend/app/services/log_filter.py's
// INTERESTING_RE so "what the dashboard flags" and "what the AI prefilter scans" agree.
const FINDINGS: Finding[] = [
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

interface FindingsDashboardProps {
  events: LogEvent[];
  activeFindingId: string | null;
  onSelectFinding: (finding: Finding | null) => void;
}

export function FindingsDashboard({ events, activeFindingId, onSelectFinding }: FindingsDashboardProps) {
  const counts = useMemo(
    () =>
      FINDINGS.map((finding) => ({
        finding,
        count: events.reduce((n, e) => (finding.regex.test(e.message) ? n + 1 : n), 0),
      })).filter((c) => c.count > 0),
    [events]
  );

  if (counts.length === 0) return null;

  return (
    <div className="findings-dashboard" role="group" aria-label="Common findings">
      {counts.map(({ finding, count }) => {
        const isActive = activeFindingId === finding.id;
        return (
          <button
            key={finding.id}
            type="button"
            className={`finding-tile finding-${finding.severity}${isActive ? " active" : ""}`}
            aria-pressed={isActive}
            onClick={() => onSelectFinding(isActive ? null : finding)}
            title={`${isActive ? "Clear filter" : "Filter to"}: ${finding.label}`}
          >
            <span className="finding-count">{count.toLocaleString()}</span>
            <span className="finding-label">{finding.label}</span>
          </button>
        );
      })}
    </div>
  );
}
