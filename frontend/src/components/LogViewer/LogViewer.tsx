import { useEffect, useState, type KeyboardEvent } from "react";
import { List, useListRef, type RowComponentProps } from "react-window";

import type { LogEvent } from "../../api/types";
import { useSelectionStore } from "../../state/selectionStore";
import { formatTimestamp } from "../../utils/time";

interface RowProps {
  events: LogEvent[];
  highlightStart: number | null;
  highlightEnd: number | null;
  focusedIndex: number;
}

function Row({
  index,
  style,
  events,
  highlightStart,
  highlightEnd,
  focusedIndex,
}: RowComponentProps<RowProps>) {
  const event = events[index];
  const isHighlighted =
    highlightStart !== null &&
    highlightEnd !== null &&
    event.line_index >= highlightStart &&
    event.line_index <= highlightEnd;

  const classNames = ["log-row"];
  if (index % 2 === 1) classNames.push("odd");
  if (isHighlighted) classNames.push("highlighted");
  if (index === focusedIndex) classNames.push("focused");

  return (
    <div
      style={style}
      className={classNames.join(" ")}
      title={event.message}
      role="row"
      aria-rowindex={index + 1}
      aria-selected={index === focusedIndex}
    >
      <span className="log-index">{event.line_index}</span>
      <span className="log-timestamp">{formatTimestamp(event.timestamp)}</span>
      <span className="log-message">{event.message}</span>
    </div>
  );
}

export function LogViewer() {
  const events = useSelectionStore((s) => s.events);
  const highlightedRange = useSelectionStore((s) => s.highlightedRange);
  const setHighlightedRange = useSelectionStore((s) => s.setHighlightedRange);
  const listRef = useListRef(null);
  const [focusedIndex, setFocusedIndex] = useState(0);

  useEffect(() => {
    if (highlightedRange && listRef.current) {
      try {
        listRef.current.scrollToRow({ index: highlightedRange.start, align: "center" });
        setFocusedIndex(highlightedRange.start);
      } catch {
        // index falls outside the currently loaded event list; nothing to scroll to
      }
    }
  }, [highlightedRange, listRef]);

  useEffect(() => {
    setFocusedIndex(0);
  }, [events]);

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (events.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      const next = Math.min(focusedIndex + 1, events.length - 1);
      setFocusedIndex(next);
      listRef.current?.scrollToRow({ index: next, align: "auto" });
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      const next = Math.max(focusedIndex - 1, 0);
      setFocusedIndex(next);
      listRef.current?.scrollToRow({ index: next, align: "auto" });
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      const event = events[focusedIndex];
      if (event) setHighlightedRange({ start: event.line_index, end: event.line_index });
    }
  };

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
    <div
      className="log-viewer"
      role="log"
      aria-label="Log lines"
      aria-rowcount={events.length}
      tabIndex={0}
      onKeyDown={handleKeyDown}
    >
      <List
        listRef={listRef}
        rowComponent={Row}
        rowCount={events.length}
        rowHeight={28}
        rowProps={{
          events,
          highlightStart: highlightedRange?.start ?? null,
          highlightEnd: highlightedRange?.end ?? null,
          focusedIndex,
        }}
        style={{ height: "100%", width: "100%" }}
      />
    </div>
  );
}
