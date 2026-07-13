import { useEffect } from "react";
import { List, useListRef, type RowComponentProps } from "react-window";

import type { LogEvent } from "../../api/types";
import { useSelectionStore } from "../../state/selectionStore";
import { formatTimestamp } from "../../utils/time";

interface RowProps {
  events: LogEvent[];
  highlightStart: number | null;
  highlightEnd: number | null;
}

function Row({ index, style, events, highlightStart, highlightEnd }: RowComponentProps<RowProps>) {
  const event = events[index];
  const isHighlighted =
    highlightStart !== null &&
    highlightEnd !== null &&
    event.line_index >= highlightStart &&
    event.line_index <= highlightEnd;

  const classNames = ["log-row"];
  if (index % 2 === 1) classNames.push("odd");
  if (isHighlighted) classNames.push("highlighted");

  return (
    <div style={style} className={classNames.join(" ")} title={event.message}>
      <span className="log-index">{event.line_index}</span>
      <span className="log-timestamp">{formatTimestamp(event.timestamp)}</span>
      <span className="log-message">{event.message}</span>
    </div>
  );
}

export function LogViewer() {
  const events = useSelectionStore((s) => s.events);
  const highlightedRange = useSelectionStore((s) => s.highlightedRange);
  const listRef = useListRef(null);

  useEffect(() => {
    if (highlightedRange && listRef.current) {
      try {
        listRef.current.scrollToRow({ index: highlightedRange.start, align: "center" });
      } catch {
        // index falls outside the currently loaded event list; nothing to scroll to
      }
    }
  }, [highlightedRange, listRef]);

  if (events.length === 0) {
    return (
      <div className="log-viewer-empty">
        <span className="empty-icon">☰</span>
        <span className="empty-title">No logs loaded</span>
        <span className="empty-subtitle">
          Pick a source and time range on the left, then search or load objects to begin.
        </span>
      </div>
    );
  }

  return (
    <div className="log-viewer">
      <List
        listRef={listRef}
        rowComponent={Row}
        rowCount={events.length}
        rowHeight={28}
        rowProps={{
          events,
          highlightStart: highlightedRange?.start ?? null,
          highlightEnd: highlightedRange?.end ?? null,
        }}
        style={{ height: "100%", width: "100%" }}
      />
    </div>
  );
}
