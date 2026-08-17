import { format } from 'date-fns'
import { useMemo, useState } from 'react'

import type { LogEvent } from '../../api/types'
import { facetColor } from '../../utils/facetColors'
import { extractLogFacets, type LogFacetKey, type LogFacetSelection } from '../../utils/logFacets'

const BUCKET_COUNT = 96
const CHART_HEIGHT = 48
const FACET_ORDER: LogFacetKey[] = ['level', 'method', 'route', 'status', 'exception', 'duration']
const DEFAULT_SEGMENT = 'All logs'

interface Bucket {
  start: Date
  end: Date
  count: number
  facetCounts: Map<string, number>
  minLineIndex: number | null
  maxLineIndex: number | null
}

function buildBuckets(events: LogEvent[], rangeStart: Date, rangeEnd: Date, colorFacet: LogFacetKey | null): Bucket[] {
  const startMs = rangeStart.getTime()
  const endMs = rangeEnd.getTime()
  const bucketMs = (endMs - startMs) / BUCKET_COUNT
  const buckets = Array.from({ length: BUCKET_COUNT }, (_, index): Bucket => ({
    start: new Date(startMs + index * bucketMs),
    end: new Date(startMs + (index + 1) * bucketMs),
    count: 0,
    facetCounts: new Map<string, number>(),
    minLineIndex: null,
    maxLineIndex: null,
  }))

  for (const event of events) {
    if (!event.timestamp) continue
    const timestamp = new Date(event.timestamp).getTime()
    if (Number.isNaN(timestamp) || timestamp < startMs || timestamp > endMs) continue
    const index = Math.min(BUCKET_COUNT - 1, Math.max(0, Math.floor((timestamp - startMs) / bucketMs)))
    const bucket = buckets[index]
    const value = colorFacet ? extractLogFacets(event)[colorFacet] ?? 'Other' : DEFAULT_SEGMENT
    bucket.count += 1
    bucket.facetCounts.set(value, (bucket.facetCounts.get(value) ?? 0) + 1)
    bucket.minLineIndex = bucket.minLineIndex === null ? event.line_index : Math.min(bucket.minLineIndex, event.line_index)
    bucket.maxLineIndex = bucket.maxLineIndex === null ? event.line_index : Math.max(bucket.maxLineIndex, event.line_index)
  }
  return buckets
}

function bucketLabel(start: Date, end: Date) {
  return `${format(start, 'MMM d, HH:mm')} – ${format(end, 'HH:mm')}`
}

interface LogVolumeChartProps {
  events: LogEvent[]
  rangeStart: string
  rangeEnd: string
  facetSelection: LogFacetSelection
  onFacetChange: (selection: LogFacetSelection) => void
  onBucketClick?: (range: { start: number; end: number }) => void
}

export function LogVolumeChart({ events, rangeStart, rangeEnd, facetSelection, onFacetChange, onBucketClick }: LogVolumeChartProps) {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null)
  const range = useMemo(() => {
    const start = new Date(rangeStart)
    const end = new Date(rangeEnd)
    return Number.isNaN(start.getTime()) || Number.isNaN(end.getTime()) || end <= start ? null : { start, end }
  }, [rangeStart, rangeEnd])
  const colorFacet = FACET_ORDER.find((key) => facetSelection[key].length > 0) ?? null
  const buckets = useMemo(
    () => range ? buildBuckets(events, range.start, range.end, colorFacet) : [],
    [events, range, colorFacet],
  )

  if (!range || buckets.length === 0) return null
  const maxCount = Math.max(1, ...buckets.map((bucket) => bucket.count))
  const hovered = hoveredIndex === null ? null : buckets[hoveredIndex]
  const toggleFacet = (value: string) => {
    if (!colorFacet || value === 'Other' || value === DEFAULT_SEGMENT) return
    const selected = facetSelection[colorFacet]
    onFacetChange({
      ...facetSelection,
      [colorFacet]: selected.includes(value) ? selected.filter((item) => item !== value) : [...selected, value],
    })
  }

  return (
    <div className="log-volume-chart">
      <div className="log-volume-color-label">
        {colorFacet ? <>Colored by selected <strong>{colorFacet.replace('_', ' ')}</strong></> : <strong>All logs</strong>}
      </div>
      {hovered && (
        <div className="log-volume-tooltip" role="status">
          <strong>{hovered.count.toLocaleString()} lines</strong>
          <span>{[...hovered.facetCounts].sort((a, b) => b[1] - a[1]).slice(0, 4).map(([value, count]) => `${value}: ${count}`).join(' · ')}</span>
          <span className="log-volume-tooltip-range">{bucketLabel(hovered.start, hovered.end)}</span>
        </div>
      )}
      <div className="log-volume-bars" style={{ height: CHART_HEIGHT }}>
        {buckets.map((bucket, index) => {
          const height = bucket.count === 0 ? 0 : Math.max(2, Math.round((bucket.count / maxCount) * CHART_HEIGHT))
          const hasData = bucket.count > 0 && bucket.minLineIndex !== null && bucket.maxLineIndex !== null
          const activateBucket = () => hasData && onBucketClick?.({ start: bucket.minLineIndex!, end: bucket.maxLineIndex! })
          return (
            <div
              key={index}
              className={`log-volume-bar${hoveredIndex === index ? ' hovered' : ''}${hasData ? ' clickable' : ''}`}
              style={{ height }}
              tabIndex={hasData ? 0 : -1}
              role={hasData ? 'button' : 'graphics-symbol'}
              aria-label={`${bucket.count} lines, ${bucketLabel(bucket.start, bucket.end)}`}
              onMouseEnter={() => setHoveredIndex(index)}
              onMouseLeave={() => setHoveredIndex((value) => value === index ? null : value)}
              onFocus={() => setHoveredIndex(index)}
              onBlur={() => setHoveredIndex((value) => value === index ? null : value)}
              onClick={activateBucket}
              onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === ' ') {
                  event.preventDefault()
                  activateBucket()
                }
              }}
            >
              {[...bucket.facetCounts].sort((a, b) => a[0].localeCompare(b[0])).map(([value, count]) => {
                const selected = colorFacet ? facetSelection[colorFacet] : []
                const inactive = selected.length > 0 && !selected.includes(value)
                const canFilter = colorFacet !== null && value !== 'Other'
                const color = colorFacet ? facetColor(colorFacet, value) : 'var(--severity-success)'
                return <span key={value} className={`log-volume-segment${inactive ? ' inactive' : ''}`} style={{ height: `${(count / bucket.count) * 100}%`, background: color }} role={canFilter ? 'button' : undefined} tabIndex={canFilter ? 0 : undefined} title={canFilter ? `Filter ${colorFacet} by ${value}` : undefined} onClick={canFilter ? (event) => { event.stopPropagation(); toggleFacet(value) } : undefined} onKeyDown={canFilter ? (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); event.stopPropagation(); toggleFacet(value) } } : undefined} />
              })}
            </div>
          )
        })}
      </div>
      <div className="log-volume-axis"><span>{format(range.start, 'MMM d, HH:mm')}</span><span>{format(range.end, 'MMM d, HH:mm')}</span></div>
    </div>
  )
}
