import { useMemo } from 'react'

import type { LogEvent } from '../../api/types'
import type { Finding, FindingSeverity } from '../../utils/findings'
import type { LogFacetSelection } from '../../utils/logFacets'
import { formatSingaporeDateTime } from '../../utils/time'
import { LogFacetFilters } from './LogFacetFilters'

const HTTP_STATUS_DEFS = [
  { code: '1xx', label: 'Info', color: 'var(--status-1xx)', regex: /\b1\d{2}\b/, severity: 'info' },
  { code: '2xx', label: 'Success', color: 'var(--status-2xx)', regex: /\b2\d{2}\b/, severity: 'info' },
  { code: '3xx', label: 'Redirection', color: 'var(--status-3xx)', regex: /\b3\d{2}\b/, severity: 'info' },
  { code: '4xx', label: 'Client Error', color: 'var(--status-4xx)', regex: /\b4\d{2}\b/, severity: 'warning' },
  { code: '5xx', label: 'Server Error', color: 'var(--status-5xx)', regex: /\b5\d{2}\b/, severity: 'critical' },
] as const

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
  const series = useMemo(() => {
    const dated = events.map((event) => ({ event, date: eventDate(event) })).filter((item) => item.date) as Array<{ event: LogEvent; date: Date }>
    if (!dated.length) return {
      labels: [],
      statuses: HTTP_STATUS_DEFS.map((status) => ({ ...status, values: Array<number>(12).fill(0) })),
    }
    const start = Math.min(...dated.map((item) => item.date.getTime()))
    const end = Math.max(...dated.map((item) => item.date.getTime()))
    const span = Math.max(1, end - start)
    const buckets = Array.from({ length: 12 }, () => Array<number>(HTTP_STATUS_DEFS.length).fill(0))
    dated.forEach(({ event, date }) => {
      const index = Math.min(11, Math.floor(((date.getTime() - start) / span) * 12))
      HTTP_STATUS_DEFS.forEach((status, statusIndex) => {
        if (status.regex.test(event.message)) buckets[index][statusIndex] += 1
      })
    })
    return {
      labels: Array.from({ length: 4 }, (_, index) => formatSingaporeDateTime(new Date(start + (span * index) / 3))),
      statuses: HTTP_STATUS_DEFS.map((status, statusIndex) => ({
        ...status,
        values: buckets.map((bucket) => bucket[statusIndex]),
      })),
    }
  }, [events])
  const statusTotals = useMemo(() => HTTP_STATUS_DEFS.map((status) => ({
    ...status,
    count: events.filter((event) => status.regex.test(event.message)).length,
  })), [events])

  const max = Math.max(1, ...series.statuses.flatMap((status) => status.values))
  const points = (values: number[]) => values.map((value, index) => `${28 + index * 62},${176 - (value / max) * 138}`).join(' ')

  return (
    <div className="comparison-chart">
      <div className="comparison-summary">
        {statusTotals.map((status) => {
          const id = `dashboard-${status.code}`
          return <button type="button" key={status.code} className={activeFindingId === id ? 'active' : ''} aria-pressed={activeFindingId === id} onClick={() => toggleFinding(id, `${status.code} - ${status.label}`, status.regex, status.severity, activeFindingId, onSelectFinding)}><span style={{ color: status.color }}>{status.code} - {status.label}</span><strong>{status.count.toLocaleString()}</strong></button>
        })}
      </div>
      <svg viewBox="0 0 740 210" role="img" aria-label="HTTP status code trends over time">
        {[38, 84, 130, 176].map((y) => <line key={y} x1="28" x2="710" y1={y} y2={y} className="grid-line" />)}
        <text x="4" y="42" className="chart-y-label">{max}</text>
        <text x="4" y="110" className="chart-y-label">{Math.round(max / 2)}</text>
        <text x="14" y="180" className="chart-y-label">0</text>
        {series.statuses.map((status) => <polyline key={status.code} points={points(status.values)} className="line-series" style={{ stroke: status.color }} />)}
        {series.statuses.flatMap((status) => status.values.map((value, index) => <circle key={`${status.code}-${index}`} cx={28 + index * 62} cy={176 - (value / max) * 138} r="3.2" className="status-code-dot" style={{ fill: status.color }}><title>{status.code} {status.label}: {value}</title></circle>))}
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
      <article className="dashboard-card comparison-card"><h2>HTTP Status Overview</h2><LineChart {...chartProps} /></article>
      <article className="dashboard-card status-card"><h2>Status</h2><StatusDonut {...chartProps} /></article>
      <article className="dashboard-card facets-card"><LogFacetFilters events={events} selection={facetSelection} onChange={onFacetChange} /></article>
    </section>
  )
}
