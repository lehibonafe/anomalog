import { format } from "date-fns";
import { useMemo, useState } from "react";

import type { LogEvent } from "../../api/types";

const BUCKET_COUNT = 48;

interface Bucket {
  start: Date;
  end: Date;
  count: number;
}

function buildBuckets(events: LogEvent[], rangeStart: Date, rangeEnd: Date): Bucket[] {
  const startMs = rangeStart.getTime();
  const endMs = rangeEnd.getTime();
  const span = endMs - startMs;
  const bucketMs = span / BUCKET_COUNT;

  const buckets: Bucket[] = Array.from({ length: BUCKET_COUNT }, (_, i) => ({
    start: new Date(startMs + i * bucketMs),
    end: new Date(startMs + (i + 1) * bucketMs),
    count: 0,
  }));

  for (const event of events) {
    if (!event.timestamp) continue;
    const t = new Date(event.timestamp).getTime();
    if (Number.isNaN(t) || t < startMs || t > endMs) continue;
    const idx = Math.min(BUCKET_COUNT - 1, Math.max(0, Math.floor((t - startMs) / bucketMs)));
    buckets[idx].count += 1;
  }

  return buckets;
}

function bucketLabel(start: Date, end: Date): string {
  return `${format(start, "MMM d, HH:mm")} – ${format(end, "HH:mm")}`;
}

interface LogVolumeChartProps {
  events: LogEvent[];
  rangeStart: string;
  rangeEnd: string;
}

const CHART_HEIGHT = 48;

export function LogVolumeChart({ events, rangeStart, rangeEnd }: LogVolumeChartProps) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  const range = useMemo(() => {
    const start = new Date(rangeStart);
    const end = new Date(rangeEnd);
    if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end <= start) return null;
    return { start, end };
  }, [rangeStart, rangeEnd]);

  const buckets = useMemo(
    () => (range ? buildBuckets(events, range.start, range.end) : []),
    [events, range]
  );

  if (!range || buckets.length === 0) return null;

  const maxCount = Math.max(1, ...buckets.map((b) => b.count));
  const hovered = hoveredIndex !== null ? buckets[hoveredIndex] : null;

  return (
    <div className="log-volume-chart">
      {hovered && (
        <div className="log-volume-tooltip" role="status">
          <strong>{hovered.count.toLocaleString()}</strong> lines
          <span className="log-volume-tooltip-range">{bucketLabel(hovered.start, hovered.end)}</span>
        </div>
      )}
      <div className="log-volume-bars" style={{ height: CHART_HEIGHT }}>
        {buckets.map((bucket, i) => {
          const heightPx = bucket.count === 0 ? 0 : Math.max(2, Math.round((bucket.count / maxCount) * CHART_HEIGHT));
          return (
            <div
              key={i}
              className={`log-volume-bar${hoveredIndex === i ? " hovered" : ""}`}
              style={{ height: heightPx }}
              tabIndex={bucket.count > 0 ? 0 : -1}
              role="graphics-symbol"
              aria-label={`${bucket.count} lines, ${bucketLabel(bucket.start, bucket.end)}`}
              onMouseEnter={() => setHoveredIndex(i)}
              onMouseLeave={() => setHoveredIndex((v) => (v === i ? null : v))}
              onFocus={() => setHoveredIndex(i)}
              onBlur={() => setHoveredIndex((v) => (v === i ? null : v))}
            />
          );
        })}
      </div>
      <div className="log-volume-axis">
        <span>{format(range.start, "MMM d, HH:mm")}</span>
        <span>{format(range.end, "MMM d, HH:mm")}</span>
      </div>
    </div>
  );
}
