import { useEffect, useState } from 'react'

import { CloudTrailSearchBar } from './components/FilterBar/CloudTrailSearchBar'
import { FilterBar } from './components/FilterBar/FilterBar'
import { LogSummary } from './components/LogSummary/LogSummary'
import { ModelSettingsControl } from './components/LogSummary/ModelSettingsControl'
import { LogViewer } from './components/LogViewer/LogViewer'
import { AnalyticsDashboard } from './components/LogViewer/AnalyticsDashboard'
import { SourceSelector } from './components/SourceSelector/SourceSelector'
import { TimeRangePicker } from './components/TimeRangePicker/TimeRangePicker'
import { useSelectionStore } from './state/selectionStore'
import type { Finding } from './utils/findings'
import { EMPTY_LOG_FACETS, type LogFacetSelection } from './utils/logFacets'
import './App.css'

function App() {
  const events = useSelectionStore((s) => s.events)
  const sourceDescription = useSelectionStore((s) => s.sourceDescription)
  const [activeFinding, setActiveFinding] = useState<Finding | null>(null)
  const [facetSelection, setFacetSelection] = useState<LogFacetSelection>(EMPTY_LOG_FACETS)
  const [visibleEvents, setVisibleEvents] = useState<typeof events>([])

  useEffect(() => {
    setFacetSelection(EMPTY_LOG_FACETS)
    setVisibleEvents([])
  }, [sourceDescription])

  return (
    <div className="app-layout">
      <header className="app-header">
        <span className="logo-dot" />
        <h1>Anomalog</h1>
        <ModelSettingsControl />
      </header>
      <div className="app-body">
        <aside className="sidebar">
          <SourceSelector />
          <TimeRangePicker />
          <FilterBar />
          <CloudTrailSearchBar />
        </aside>
        <main className="main-content">
          <LogSummary events={visibleEvents} />
          <AnalyticsDashboard
            events={events}
            activeFindingId={activeFinding?.id ?? null}
            onSelectFinding={setActiveFinding}
            facetSelection={facetSelection}
            onFacetChange={setFacetSelection}
          />
          <section className="raw-logs-section">
            <div className="raw-logs-title">Log details</div>
            <LogViewer
              activeFinding={activeFinding}
              onSelectFinding={setActiveFinding}
              facetSelection={facetSelection}
              onFacetChange={setFacetSelection}
              onVisibleEventsChange={setVisibleEvents}
            />
          </section>
        </main>
      </div>
    </div>
  )
}

export default App
