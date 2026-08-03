import { useEffect, useMemo, useState, type KeyboardEvent } from "react";
import { List, useListRef, type RowComponentProps } from "react-window";

import type { LogEvent } from "../../api/types";
import { useSelectionStore } from "../../state/selectionStore";
import { formatTimestamp } from "../../utils/time";
import { LogVolumeChart } from "./LogVolumeChart";

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
  const startTime = useSelectionStore((s) => s.startTime);
  const endTime = useSelectionStore((s) => s.endTime);
  const listRef = useListRef(null);
  const [focusedIndex, setFocusedIndex] = useState(0);
  const [keyword, setKeyword] = useState("");

  const filteredEvents = useMemo(() => {
    const term = keyword.trim().toLowerCase();
    if (!term) return events;
    return events.filter((e) => e.message.toLowerCase().includes(term));
  }, [events, keyword]);

  useEffect(() => {
    if (highlightedRange && listRef.current) {
      const idx = filteredEvents.findIndex((e) => e.line_index === highlightedRange.start);
      if (idx === -1) return;
      try {
        listRef.current.scrollToRow({ index: idx, align: "center" });
        setFocusedIndex(idx);
      } catch {
        // index falls outside the currently loaded event list; nothing to scroll to
      }
    }
  }, [highlightedRange, listRef, filteredEvents]);

  useEffect(() => {
    setFocusedIndex(0);
  }, [events, keyword]);

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (filteredEvents.length === 0) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      const next = Math.min(focusedIndex + 1, filteredEvents.length - 1);
      setFocusedIndex(next);
      listRef.current?.scrollToRow({ index: next, align: "auto" });
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      const next = Math.max(focusedIndex - 1, 0);
      setFocusedIndex(next);
      listRef.current?.scrollToRow({ index: next, align: "auto" });
    } else if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      const event = filteredEvents[focusedIndex];
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
    <div className="log-viewer-panel">
      <div className="log-filter-row">
        <input
          type="text"
          className="log-filter-input"
          placeholder="Filter by keyword..."
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
        />
        <span className="log-filter-count">
          {filteredEvents.length.toLocaleString()} / {events.length.toLocaleString()} lines
        </span>
      </div>
      {startTime && endTime && (
        <LogVolumeChart events={filteredEvents} rangeStart={startTime} rangeEnd={endTime} />
      )}
      {filteredEvents.length === 0 ? (
        <div className="log-viewer-empty">
          <span className="empty-icon">☰</span>
          <span className="empty-title">No matching lines</span>
          <span className="empty-subtitle">No lines contain “{keyword.trim()}”.</span>
        </div>
      ) : (
        <div
          className="log-viewer"
          role="log"
          aria-label="Log lines"
          aria-rowcount={filteredEvents.length}
          tabIndex={0}
          onKeyDown={handleKeyDown}
        >
          <List
            listRef={listRef}
            rowComponent={Row}
            rowCount={filteredEvents.length}
            rowHeight={28}
            rowProps={{
              events: filteredEvents,
              highlightStart: highlightedRange?.start ?? null,
              highlightEnd: highlightedRange?.end ?? null,
              focusedIndex,
            }}
            style={{ height: "100%", width: "100%" }}
          />
        </div>
      )}
    </div>
  );
}
