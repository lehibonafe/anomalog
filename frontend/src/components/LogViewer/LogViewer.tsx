import { useCallback, useEffect, useMemo, useState, type KeyboardEvent } from "react";
import { List, useDynamicRowHeight, useListRef, type RowComponentProps } from "react-window";

import type { LogEvent } from "../../api/types";
import { useSelectionStore } from "../../state/selectionStore";
import { getLineSeverity, splitHighlighted, type Finding } from "../../utils/findings";
import { extractJson } from "../../utils/jsonExtract";
import { formatTimestamp } from "../../utils/time";
import { FindingsDashboard } from "./FindingsDashboard";
import { JsonBlock } from "./JsonView";
import { LogVolumeChart } from "./LogVolumeChart";

interface RowProps {
  events: LogEvent[];
  highlightStart: number | null;
  highlightEnd: number | null;
  focusedIndex: number;
  expandedLines: Set<number>;
  onToggleExpand: (lineIndex: number) => void;
}

function HighlightedText({ text }: { text: string }) {
  const segments = useMemo(() => splitHighlighted(text), [text]);
  return (
    <>
      {segments.map((seg, i) =>
        seg.severity ? (
          <mark key={i} className={`log-highlight log-highlight-${seg.severity}`}>
            {seg.text}
          </mark>
        ) : (
          seg.text
        )
      )}
    </>
  );
}

function Row({
  index,
  style,
  events,
  highlightStart,
  highlightEnd,
  focusedIndex,
  expandedLines,
  onToggleExpand,
}: RowComponentProps<RowProps>) {
  const event = events[index];
  const isHighlighted =
    highlightStart !== null &&
    highlightEnd !== null &&
    event.line_index >= highlightStart &&
    event.line_index <= highlightEnd;
  const isExpanded = expandedLines.has(event.line_index);
  const severity = useMemo(() => getLineSeverity(event.message), [event.message]);
  const json = useMemo(() => (isExpanded ? extractJson(event.message) : null), [isExpanded, event.message]);

  const classNames = ["log-row"];
  if (index % 2 === 1) classNames.push("odd");
  if (severity) classNames.push(`log-row-severity-${severity}`);
  if (isHighlighted) classNames.push("highlighted");
  if (index === focusedIndex) classNames.push("focused");
  if (isExpanded) classNames.push("expanded");

  return (
    <div
      style={style}
      className={classNames.join(" ")}
      title={isExpanded ? undefined : event.message}
      role="row"
      aria-rowindex={index + 1}
      aria-selected={index === focusedIndex}
    >
      <button
        type="button"
        className="log-row-toggle"
        aria-expanded={isExpanded}
        aria-label={isExpanded ? "Collapse line" : "Expand line"}
        onClick={(e) => {
          e.stopPropagation();
          onToggleExpand(event.line_index);
        }}
      >
        <span className="log-row-toggle-icon" aria-hidden="true">
          ▸
        </span>
      </button>
      <span className="log-index">{event.line_index}</span>
      <span className="log-timestamp">{formatTimestamp(event.timestamp)}</span>
      <div className="log-message">
        {json ? (
          <>
            {json.prefix && <HighlightedText text={json.prefix} />}
            <JsonBlock value={json.value} />
            {json.suffix && <HighlightedText text={json.suffix} />}
          </>
        ) : (
          <HighlightedText text={event.message} />
        )}
      </div>
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
  const [activeFinding, setActiveFinding] = useState<Finding | null>(null);
  const [expandedLines, setExpandedLines] = useState<Set<number>>(new Set());
  const rowHeight = useDynamicRowHeight({ defaultRowHeight: 28 });

  const toggleExpand = useCallback((lineIndex: number) => {
    setExpandedLines((prev) => {
      const next = new Set(prev);
      if (next.has(lineIndex)) {
        next.delete(lineIndex);
      } else {
        next.add(lineIndex);
      }
      return next;
    });
  }, []);

  const filteredEvents = useMemo(() => {
    const term = keyword.trim().toLowerCase();
    return events.filter((e) => {
      if (term && !e.message.toLowerCase().includes(term)) return false;
      if (activeFinding && !activeFinding.regex.test(e.message)) return false;
      return true;
    });
  }, [events, keyword, activeFinding]);

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
  }, [events, keyword, activeFinding]);

  useEffect(() => {
    setActiveFinding(null);
    setExpandedLines(new Set());
  }, [events]);

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
      <FindingsDashboard
        events={events}
        activeFindingId={activeFinding?.id ?? null}
        onSelectFinding={setActiveFinding}
      />
      {startTime && endTime && (
        <LogVolumeChart
          events={filteredEvents}
          rangeStart={startTime}
          rangeEnd={endTime}
          onBucketClick={setHighlightedRange}
        />
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
            rowHeight={rowHeight}
            rowProps={{
              events: filteredEvents,
              highlightStart: highlightedRange?.start ?? null,
              highlightEnd: highlightedRange?.end ?? null,
              focusedIndex,
              expandedLines,
              onToggleExpand: toggleExpand,
            }}
            style={{ height: "100%", width: "100%" }}
          />
        </div>
      )}
    </div>
  );
}
