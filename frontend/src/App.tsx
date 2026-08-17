import { useEffect, useState } from 'react'

import { ChatWidget } from './components/ChatWidget/ChatWidget'
import { CloudTrailSearchBar } from './components/FilterBar/CloudTrailSearchBar'
import { FilterBar } from './components/FilterBar/FilterBar'
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

  useEffect(() => {
    setFacetSelection(EMPTY_LOG_FACETS)
  }, [sourceDescription])

  return (
    <div className="app-layout">
      <header className="app-header">
        <span className="logo-dot" />
        <h1>CloudCortex</h1>
      </header>
      <div className="app-body">
        <aside className="sidebar">
          <SourceSelector />
          <TimeRangePicker />
          <FilterBar />
          <CloudTrailSearchBar />
        </aside>
        <main className="main-content">
          <div className="log-viewer-header">
            <span className="source-label">{sourceDescription || 'No logs loaded'}</span>
            <span className="hint">{events.length} lines</span>
          </div>
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
            />
          </section>
        </main>
      </div>
      <ChatWidget />
    </div>
  )
}

export default App
