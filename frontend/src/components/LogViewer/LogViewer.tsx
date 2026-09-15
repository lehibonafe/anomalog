import { useCallback, useEffect, useMemo, useState, type KeyboardEvent } from "react";
import { List, useDynamicRowHeight, useListRef, type RowComponentProps } from "react-window";

import type { LogEvent } from "../../api/types";
import { useSelectionStore } from "../../state/selectionStore";
import { splitHighlighted, type Finding } from "../../utils/findings";
import { facetColor } from "../../utils/facetColors";
import { extractLogFacets, findSelectedFacetMatches, matchesLogFacets, type LogFacetSelection } from "../../utils/logFacets";
import { extractJson } from "../../utils/jsonExtract";
import { formatTimestamp } from "../../utils/time";
import { JsonBlock } from "./JsonView";
import { LogVolumeChart } from "./LogVolumeChart";

interface RowProps {
  events: LogEvent[];
  keyword: string;
  activeFinding: Finding | null;
  highlightRanges: Array<{ start: number; end: number }>;
  focusedIndex: number;
  expandedLines: Set<number>;
  onToggleExpand: (lineIndex: number) => void;
  facetSelection: LogFacetSelection;
}

interface DisplaySegment {
  text: string;
  className: string | null;
  color: string | null;
}

interface HighlightRange {
  start: number;
  end: number;
  className: string;
  priority: number;
  color?: string;
}

function regexRanges(text: string, regex: RegExp, className: string, priority: number): HighlightRange[] {
  const flags = `${regex.flags.replace(/[gy]/g, "")}g`;
  const globalRegex = new RegExp(regex.source, flags);
  return [...text.matchAll(globalRegex)]
    .filter((match) => match[0].length > 0)
    .map((match) => ({
      start: match.index ?? 0,
      end: (match.index ?? 0) + match[0].length,
      className,
      priority,
    }));
}

function splitDisplayHighlights(event: LogEvent, text: string, keyword: string, activeFinding: Finding | null, facetSelection: LogFacetSelection): DisplaySegment[] {
  const ranges: HighlightRange[] = [];
  let offset = 0;
  for (const segment of splitHighlighted(text)) {
    if (segment.severity) {
      ranges.push({
        start: offset,
        end: offset + segment.text.length,
        className: `log-highlight-${segment.severity}`,
        priority: 1,
      });
    }
    offset += segment.text.length;
  }

  if (activeFinding) {
    ranges.push(...regexRanges(text, activeFinding.regex, `log-highlight-${activeFinding.severity}`, 2));
  }

  for (const match of findSelectedFacetMatches(event, facetSelection)) {
    ranges.push({ start: match.start, end: match.end, className: "log-highlight-facet", priority: 3, color: facetColor(match.key, match.value) });
  }

  const term = keyword.trim();
  if (term) {
    const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    ranges.push(...regexRanges(text, new RegExp(escaped, "i"), "log-highlight-keyword", 4));
  }

  const boundaries = [...new Set([0, text.length, ...ranges.flatMap((range) => [range.start, range.end])])]
    .filter((value) => value >= 0 && value <= text.length)
    .sort((a, b) => a - b);

  const segments: DisplaySegment[] = [];
  for (let index = 0; index < boundaries.length - 1; index += 1) {
    const start = boundaries[index];
    const end = boundaries[index + 1];
    const selected = ranges
      .filter((range) => range.start <= start && range.end >= end)
      .sort((a, b) => b.priority - a.priority)[0];
    const className = selected?.className ?? null;
    const color = selected?.color ?? null;
    const previous = segments[segments.length - 1];
    if (previous?.className === className && previous.color === color) previous.text += text.slice(start, end);
    else segments.push({ text: text.slice(start, end), className, color });
  }
  return segments;
}

function HighlightedText({ event, text, keyword, activeFinding, facetSelection }: { event: LogEvent; text: string; keyword: string; activeFinding: Finding | null; facetSelection: LogFacetSelection }) {
  const segments = useMemo(
    () => splitDisplayHighlights(event, text, keyword, activeFinding, facetSelection),
    [event, text, keyword, activeFinding, facetSelection],
  );
  return (
    <>
      {segments.map((seg, i) =>
        seg.className ? (
          <mark key={i} className={`log-highlight ${seg.className}`} style={seg.color ? { color: seg.color, backgroundColor: `${seg.color}22`, boxShadow: `inset 0 -2px 0 ${seg.color}` } : undefined}>
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
  keyword,
  activeFinding,
  highlightRanges,
  focusedIndex,
  expandedLines,
  onToggleExpand,
  facetSelection,
}: RowComponentProps<RowProps>) {
  const event = events[index];
  const isHighlighted = highlightRanges.some(
    (range) => event.line_index >= range.start && event.line_index <= range.end,
  );
  const isExpanded = expandedLines.has(event.line_index);
  const json = useMemo(() => (isExpanded ? extractJson(event.message) : null), [isExpanded, event.message]);
  const hasDynamicHighlight = keyword.trim().length > 0 || activeFinding !== null || Object.values(facetSelection).some((values) => values.length > 0);

  const classNames = ["log-row"];
  if (index % 2 === 1) classNames.push("odd");
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
        {json && !hasDynamicHighlight ? (
          <>
            {json.prefix && <HighlightedText event={event} text={json.prefix} keyword="" activeFinding={null} facetSelection={facetSelection} />}
            <JsonBlock value={json.value} />
            {json.suffix && <HighlightedText event={event} text={json.suffix} keyword="" activeFinding={null} facetSelection={facetSelection} />}
          </>
        ) : (
          <HighlightedText event={event} text={event.message} keyword={keyword} activeFinding={activeFinding} facetSelection={facetSelection} />
        )}
      </div>
    </div>
  );
}

interface LogViewerProps {
  activeFinding: Finding | null;
  onSelectFinding: (finding: Finding | null) => void;
  facetSelection: LogFacetSelection;
  onFacetChange: (selection: LogFacetSelection) => void;
  onVisibleEventsChange: (events: LogEvent[]) => void;
}

type ExportFormat = "json" | "csv" | "txt";

function csvCell(value: string | number | null) {
  let text = value === null ? "" : String(value);
  if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`;
  return `"${text.replace(/"/g, '""')}"`;
}

function serializeEvents(events: LogEvent[], format: ExportFormat) {
  if (format === "json") return JSON.stringify(events, null, 2);
  if (format === "csv") {
    const headers = ["line_index", "timestamp", "source", "origin", "stream_or_key", "message"];
    const rows = events.map((event) => [
      event.line_index,
      event.timestamp,
      event.source,
      event.origin,
      event.stream_or_key,
      event.message,
    ].map(csvCell).join(","));
    return [headers.join(","), ...rows].join("\n");
  }
  return events.map((event) => {
    const timestamp = event.timestamp ?? "No timestamp";
    return `[${timestamp}] [${event.origin}/${event.stream_or_key}] ${event.message}`;
  }).join("\n");
}

function downloadEvents(events: LogEvent[], format: ExportFormat) {
  const mimeTypes: Record<ExportFormat, string> = {
    json: "application/json;charset=utf-8",
    csv: "text/csv;charset=utf-8",
    txt: "text/plain;charset=utf-8",
  };
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
  const blob = new Blob([serializeEvents(events, format)], { type: mimeTypes[format] });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `anomalog-logs-${timestamp}.${format}`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function LogViewer({
  activeFinding,
  onSelectFinding,
  facetSelection,
  onFacetChange,
  onVisibleEventsChange,
}: LogViewerProps) {
  const events = useSelectionStore((s) => s.events);
  const sourceDescription = useSelectionStore((s) => s.sourceDescription);
  const highlightedRange = useSelectionStore((s) => s.highlightedRange);
  const setHighlightedRange = useSelectionStore((s) => s.setHighlightedRange);
  const startTime = useSelectionStore((s) => s.startTime);
  const endTime = useSelectionStore((s) => s.endTime);
  const listRef = useListRef(null);
  const [focusedIndex, setFocusedIndex] = useState(0);
  const [keyword, setKeyword] = useState("");
  const [exportFormat, setExportFormat] = useState<ExportFormat>("json");
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

  const keywordFilteredEvents = useMemo(() => {
    const term = keyword.trim().toLowerCase();
    return events.filter((event) => (
      (!term || event.message.toLowerCase().includes(term))
      && matchesLogFacets(extractLogFacets(event), facetSelection)
    ));
  }, [events, keyword, facetSelection]);

  const filteredEvents = useMemo(
    () => activeFinding
      ? keywordFilteredEvents.filter((event) => activeFinding.regex.test(event.message))
      : keywordFilteredEvents,
    [keywordFilteredEvents, activeFinding],
  );

  useEffect(() => {
    onVisibleEventsChange(filteredEvents);
  }, [filteredEvents, onVisibleEventsChange]);

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
  }, [sourceDescription, keyword, activeFinding]);

  // sourceDescription (not events) is the "this is a genuinely new search" signal —
  // appendEvents (Load more) grows `events` without changing it, so pagination
  // doesn't collapse expanded rows or clear the active finding filter.
  useEffect(() => {
    onSelectFinding(null);
    setExpandedLines(new Set());
  }, [sourceDescription, onSelectFinding]);

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
        <div className="log-export-controls">
          <select
            className="log-export-format"
            aria-label="Log export format"
            value={exportFormat}
            onChange={(event) => setExportFormat(event.target.value as ExportFormat)}
          >
            <option value="json">JSON</option>
            <option value="csv">CSV</option>
            <option value="txt">Text</option>
          </select>
          <button
            type="button"
            className="log-export-button"
            disabled={filteredEvents.length === 0}
            onClick={() => downloadEvents(filteredEvents, exportFormat)}
            title={`Export ${filteredEvents.length.toLocaleString()} filtered log lines`}
          >
            Export logs
          </button>
        </div>
      </div>
      {startTime && endTime && (
        <LogVolumeChart
          events={filteredEvents}
          rangeStart={startTime}
          rangeEnd={endTime}
          onBucketClick={setHighlightedRange}
          facetSelection={facetSelection}
          onFacetChange={onFacetChange}
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
              keyword,
              activeFinding,
              highlightRanges: highlightedRange?.ranges
                ?? (highlightedRange ? [{ start: highlightedRange.start, end: highlightedRange.end }] : []),
              focusedIndex,
              expandedLines,
              onToggleExpand: toggleExpand,
              facetSelection,
            }}
            style={{ height: "100%", width: "100%" }}
          />
        </div>
      )}
    </div>
  );
}
