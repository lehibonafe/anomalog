import { useMemo } from 'react'
import { format } from 'date-fns'

import type { LogEvent } from '../../api/types'
import { useSelectionStore } from '../../state/selectionStore'
import type { Finding, FindingSeverity } from '../../utils/findings'
import type { LogFacetSelection } from '../../utils/logFacets'
import { LogFacetFilters } from './LogFacetFilters'

const STATUS_DEFS = [
  { label: 'Succeeded', color: 'var(--severity-success)', regex: /\b(succeed(?:ed)?|success(?:ful)?)\b/i, severity: 'info' as const },
  { label: 'Started', color: 'var(--accent)', regex: /\b(start(?:ed|ing)?)\b/i, severity: 'info' as const },
  { label: 'Failed', color: 'var(--severity-critical)', regex: /\b(fail(?:ed|ure)?)\b/i, severity: 'critical' as const },
  { label: 'Updated', color: 'var(--severity-info)', regex: /\b(updat(?:ed|ing))\b/i, severity: 'info' as const },
  { label: 'Accepted', color: 'var(--json-string)', regex: /\baccepted\b/i, severity: 'info' as const },
  { label: 'Resolved', color: 'var(--json-boolean)', regex: /\bresolved\b/i, severity: 'info' as const },
  { label: 'Active', color: 'var(--severity-warning)', regex: /\bactive\b/i, severity: 'warning' as const },
]

interface AnalyticsDashboardProps {
  events: LogEvent[]
  activeFindingId: string | null
  onSelectFinding: (finding: Finding | null) => void
  facetSelection: LogFacetSelection
  onFacetChange: (selection: LogFacetSelection) => void
}

interface InteractiveChartProps {
  events: LogEvent[]
  activeFindingId: string | null
  onSelectFinding: (finding: Finding | null) => void
}

function toggleFinding(
  id: string,
  label: string,
  regex: RegExp,
  severity: FindingSeverity,
  activeFindingId: string | null,
  onSelectFinding: (finding: Finding | null) => void,
) {
  onSelectFinding(activeFindingId === id ? null : { id, label, regex, severity })
}

function eventDate(event: LogEvent) {
  const value = event.timestamp ? new Date(event.timestamp) : null
  return value && !Number.isNaN(value.getTime()) ? value : null
}

function LineChart({ events, activeFindingId, onSelectFinding }: InteractiveChartProps) {
  const highlightedRange = useSelectionStore((state) => state.highlightedRange)
  const setHighlightedRange = useSelectionStore((state) => state.setHighlightedRange)
  const series = useMemo(() => {
    const dated = events.map((event) => ({ event, date: eventDate(event) })).filter((item) => item.date) as Array<{ event: LogEvent; date: Date }>
    if (!dated.length) return { labels: [], client: [], server: [], peakRange: null, peakLabel: 'No data' }
    const start = Math.min(...dated.map((item) => item.date.getTime()))
    const end = Math.max(...dated.map((item) => item.date.getTime()))
    const span = Math.max(1, end - start)
    const buckets = Array.from({ length: 12 }, () => ({ client: 0, server: 0, lineIndexes: [] as number[] }))
    dated.forEach(({ event, date }) => {
      const index = Math.min(11, Math.floor(((date.getTime() - start) / span) * 12))
      const isClientError = /\b4\d{2}\b/.test(event.message)
      const isServerError = /\b5\d{2}\b|\b(?:exception|error|fatal)\b/i.test(event.message)
      if (isClientError) buckets[index].client += 1
      if (isServerError) buckets[index].server += 1
      if (isClientError || isServerError) buckets[index].lineIndexes.push(event.line_index)
    })
    const peakIndex = buckets.reduce((best, bucket, index) => (
      bucket.client + bucket.server > buckets[best].client + buckets[best].server ? index : best
    ), 0)
    const peakLines = buckets[peakIndex].lineIndexes
    return {
      labels: Array.from({ length: 4 }, (_, index) => format(new Date(start + (span * index) / 3), 'MMM d, HH:mm')),
      client: buckets.map((bucket) => bucket.client),
      server: buckets.map((bucket) => bucket.server),
      peakRange: peakLines.length ? { start: Math.min(...peakLines), end: Math.max(...peakLines) } : null,
      peakLabel: `${format(new Date(start + (span * peakIndex) / 12), 'MMM d, HH:mm')} – ${format(new Date(start + (span * (peakIndex + 1)) / 12), 'HH:mm')}`,
    }
  }, [events])

  const max = Math.max(1, ...series.client, ...series.server)
  const points = (values: number[]) => values.map((value, index) => `${28 + index * 62},${176 - (value / max) * 138}`).join(' ')
  const areaPoints = (values: number[]) => `28,176 ${points(values)} 710,176`
  const clientTotal = series.client.reduce((sum, value) => sum + value, 0)
  const serverTotal = series.server.reduce((sum, value) => sum + value, 0)
  const peak = Math.max(...series.client.map((value, index) => value + series.server[index]), 0)
  const peakActive = series.peakRange !== null
    && highlightedRange?.start === series.peakRange.start
    && highlightedRange?.end === series.peakRange.end

  return (
    <div className="comparison-chart">
      <div className="comparison-summary">
        <button type="button" className={activeFindingId === 'dashboard-4xx' ? 'active' : ''} aria-pressed={activeFindingId === 'dashboard-4xx'} onClick={() => toggleFinding('dashboard-4xx', '4xx client error', /\b4\d{2}\b/, 'warning', activeFindingId, onSelectFinding)}><span>Client errors</span><strong>{clientTotal.toLocaleString()}</strong><small>4xx responses</small></button>
        <button type="button" className={activeFindingId === 'dashboard-exceptions' ? 'active' : ''} aria-pressed={activeFindingId === 'dashboard-exceptions'} onClick={() => toggleFinding('dashboard-exceptions', 'Server errors & exceptions', /\b5\d{2}\b|\b(?:exception|error|fatal)\b/i, 'critical', activeFindingId, onSelectFinding)}><span>Server errors &amp; exceptions</span><strong>{serverTotal.toLocaleString()}</strong><small>5xx and application errors</small></button>
        <button type="button" className={peakActive ? 'active' : ''} aria-pressed={peakActive} disabled={!series.peakRange} onClick={() => setHighlightedRange(peakActive ? null : series.peakRange)}><span>Peak interval</span><strong>{peak.toLocaleString()}</strong><small>{series.peakLabel}</small></button>
      </div>
      <svg viewBox="0 0 740 210" role="img" aria-label="Exception comparison over time">
        <defs>
          <linearGradient id="client-area" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--severity-info)" stopOpacity=".28" /><stop offset="100%" stopColor="var(--severity-info)" stopOpacity="0" /></linearGradient>
          <linearGradient id="exception-area" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--severity-warning)" stopOpacity=".24" /><stop offset="100%" stopColor="var(--severity-warning)" stopOpacity="0" /></linearGradient>
        </defs>
        {[38, 84, 130, 176].map((y) => <line key={y} x1="28" x2="710" y1={y} y2={y} className="grid-line" />)}
        <text x="4" y="42" className="chart-y-label">{max}</text>
        <text x="4" y="110" className="chart-y-label">{Math.round(max / 2)}</text>
        <text x="14" y="180" className="chart-y-label">0</text>
        <polygon points={areaPoints(series.client)} fill="url(#client-area)" />
        <polygon points={areaPoints(series.server)} fill="url(#exception-area)" />
        <polyline points={points(series.client)} className="line-series line-blue" />
        <polyline points={points(series.server)} className="line-series line-orange" />
        {series.client.map((value, index) => <circle key={`c-${index}`} cx={28 + index * 62} cy={176 - (value / max) * 138} r="3.2" className="dot-blue"><title>Client errors: {value}</title></circle>)}
        {series.server.map((value, index) => <circle key={`s-${index}`} cx={28 + index * 62} cy={176 - (value / max) * 138} r="3.2" className="dot-orange"><title>Exceptions: {value}</title></circle>)}
      </svg>
      <div className="chart-axis">{series.labels.map((label) => <span key={label}>{label}</span>)}</div>
    </div>
  )
}

function StatusDonut({ events, activeFindingId, onSelectFinding }: InteractiveChartProps) {
  const statuses = useMemo(() => STATUS_DEFS.map((status) => ({ ...status, count: events.filter((event) => status.regex.test(event.message)).length })), [events])
  const total = Math.max(1, statuses.reduce((sum, item) => sum + item.count, 0))
  let offset = 25
  return (
    <div className="status-content">
      <div className="status-legend">
        {statuses.map((status) => {
          const id = `dashboard-status-${status.label.toLowerCase()}`
          return <button type="button" key={status.label} className={activeFindingId === id ? 'active' : ''} aria-pressed={activeFindingId === id} onClick={() => toggleFinding(id, status.label, status.regex, status.severity, activeFindingId, onSelectFinding)}><i style={{ background: status.color }} /><span>{status.label}</span><strong>{status.count.toLocaleString()}</strong></button>
        })}
      </div>
      <svg className="donut" viewBox="0 0 42 42" role="img" aria-label="Status distribution">
        <circle cx="21" cy="21" r="15.9" fill="none" stroke="var(--border-color)" strokeWidth="6" />
        {statuses.map((status) => {
          const length = (status.count / total) * 100
          const currentOffset = offset
          offset -= length
          return <circle key={status.label} cx="21" cy="21" r="15.9" fill="none" stroke={status.color} strokeWidth="6" strokeDasharray={`${length} ${100 - length}`} strokeDashoffset={currentOffset} />
        })}
        <circle cx="21" cy="21" r="11.2" className="donut-hole" />
      </svg>
    </div>
  )
}

export function AnalyticsDashboard({ events, activeFindingId, onSelectFinding, facetSelection, onFacetChange }: AnalyticsDashboardProps) {
  const chartProps = { events, activeFindingId, onSelectFinding }
  return (
    <section className="analytics-dashboard" aria-label="Log analytics dashboard">
      <article className="dashboard-card comparison-card"><h2>Error Trends</h2><LineChart {...chartProps} /></article>
      <article className="dashboard-card status-card"><h2>Status</h2><StatusDonut {...chartProps} /></article>
      <article className="dashboard-card facets-card"><LogFacetFilters events={events} selection={facetSelection} onChange={onFacetChange} /></article>
    </section>
  )
}
