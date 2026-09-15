import { useMemo, useState } from 'react'

import type { LogEvent } from '../../api/types'
import { facetColor } from '../../utils/facetColors'
import { extractLogFacets, type LogFacetKey, type LogFacetSelection } from '../../utils/logFacets'

const FACET_DEFS: Array<{ key: LogFacetKey; label: string; limit?: number }> = [
  { key: 'level', label: 'Log level' },
  { key: 'method', label: 'HTTP method' },
  { key: 'route', label: 'Route', limit: 8 },
  { key: 'status', label: 'Status' },
  { key: 'exception', label: 'Exception', limit: 8 },
  { key: 'duration', label: 'Response duration' },
]

interface LogFacetFiltersProps {
  events: LogEvent[]
  selection: LogFacetSelection
  onChange: (selection: LogFacetSelection) => void
}

export function LogFacetFilters({ events, selection, onChange }: LogFacetFiltersProps) {
  const [collapsed, setCollapsed] = useState<Set<LogFacetKey>>(new Set())
  const counts = useMemo(() => {
    const result = Object.fromEntries(FACET_DEFS.map(({ key }) => [key, new Map<string, number>()])) as Record<LogFacetKey, Map<string, number>>
    for (const event of events) {
      const facets = extractLogFacets(event)
      for (const { key } of FACET_DEFS) {
        const value = facets[key]
        if (value) result[key].set(value, (result[key].get(value) ?? 0) + 1)
      }
    }
    return result
  }, [events])

  const toggle = (key: LogFacetKey, value: string) => {
    const values = selection[key]
    onChange({ ...selection, [key]: values.includes(value) ? values.filter((item) => item !== value) : [...values, value] })
  }

  return (
    <section className="log-facets" aria-label="Log facets">
      <div className="log-facet-grid">
        {FACET_DEFS.map(({ key, label, limit }) => {
          const values = [...counts[key]].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, limit)
          const isCollapsed = collapsed.has(key)
          return (
            <div className={`log-facet-group${isCollapsed ? ' collapsed' : ''}`} key={key}>
              <h3><button type="button" aria-expanded={!isCollapsed} onClick={() => setCollapsed((current) => { const next = new Set(current); if (next.has(key)) next.delete(key); else next.add(key); return next })}>{label}<span aria-hidden="true">{isCollapsed ? '▸' : '▾'}</span></button></h3>
              {!isCollapsed && <div className="log-facet-values">
                {values.length ? values.map(([value, count]) => {
                  const active = selection[key].includes(value)
                  const color = facetColor(key, value)
                  return <button type="button" key={value} className={active ? 'active' : ''} aria-pressed={active} title={value} onClick={() => toggle(key, value)}><i className="log-facet-swatch" style={{ background: color }} /><span className="log-facet-value">{value}</span><strong>{count}</strong></button>
                }) : <span className="log-facet-empty">No values</span>}
              </div>}
            </div>
          )
        })}
      </div>
    </section>
  )
}
