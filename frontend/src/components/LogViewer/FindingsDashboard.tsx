import { useMemo } from "react";

import type { LogEvent } from "../../api/types";
import { countFindings, type Finding, type FindingSeverity } from "../../utils/findings";

const SEVERITY_ORDER: FindingSeverity[] = ["critical", "warning", "info"];
const SEVERITY_LABEL: Record<FindingSeverity, string> = {
  critical: "Critical",
  warning: "Warning",
  info: "Info",
};

interface FindingsDashboardProps {
  events: LogEvent[];
  activeFindingId: string | null;
  onSelectFinding: (finding: Finding | null) => void;
}

export function FindingsDashboard({ events, activeFindingId, onSelectFinding }: FindingsDashboardProps) {
  const counts = useMemo(() => countFindings(events), [events]);

  if (counts.length === 0) {
    return (
      <div className="findings-chart">
        <div className="findings-chart-header">
          <span className="findings-chart-title">Common findings</span>
        </div>
        <span className="hint">
          No 3xx/4xx/5xx codes or ERROR/WARN/exception keywords in the loaded lines.
        </span>
      </div>
    );
  }

  const maxCount = counts[0].count;
  const severitiesPresent = SEVERITY_ORDER.filter((s) => counts.some((c) => c.finding.severity === s));

  return (
    <div className="findings-chart">
      <div className="findings-chart-header">
        <span className="findings-chart-title">Common findings</span>
        {severitiesPresent.length > 1 && (
          <div className="findings-legend">
            {severitiesPresent.map((s) => (
              <span key={s} className={`findings-legend-item findings-${s}`}>
                <span className="findings-legend-swatch" />
                {SEVERITY_LABEL[s]}
              </span>
            ))}
          </div>
        )}
      </div>
      <div className="findings-chart-rows" role="group" aria-label="Common findings">
        {counts.map(({ finding, count }) => {
          const isActive = activeFindingId === finding.id;
          const widthPct = Math.max(4, Math.round((count / maxCount) * 100));
          const pctOfLoaded = events.length > 0 ? Math.round((count / events.length) * 100) : 0;
          return (
            <button
              key={finding.id}
              type="button"
              className={`finding-row findings-${finding.severity}${isActive ? " active" : ""}`}
              aria-pressed={isActive}
              onClick={() => onSelectFinding(isActive ? null : finding)}
              title={`${isActive ? "Clear filter" : "Filter to"}: ${finding.label} — ${count.toLocaleString()} lines (${pctOfLoaded}% of loaded)`}
            >
              <span className="finding-row-label">{finding.label}</span>
              <span className="finding-row-track">
                <span className="finding-row-bar" style={{ width: `${widthPct}%` }} />
              </span>
              <span className="finding-row-value">{count.toLocaleString()}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
