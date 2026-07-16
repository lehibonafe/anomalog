import type { Finding } from "../../api/types";
import { useSelectionStore } from "../../state/selectionStore";

export function FindingCard({ finding }: { finding: Finding }) {
  const setHighlightedRange = useSelectionStore((s) => s.setHighlightedRange);

  return (
    <div
      className="finding-card"
      onClick={() =>
        setHighlightedRange({ start: finding.line_index_start, end: finding.line_index_end })
      }
    >
      <div className="finding-header">
        <span className="severity-pill">{finding.severity}</span>
        <span>{finding.category.replace("_", " ")}</span>
        <span className="finding-lines">
          L{finding.line_index_start}–{finding.line_index_end}
        </span>
      </div>
      <div className="finding-excerpt">{finding.excerpt}</div>
      <div className="finding-explanation">{finding.explanation}</div>
    </div>
  );
}
