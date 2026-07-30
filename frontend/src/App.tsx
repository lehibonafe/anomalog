import { AnomalyPanel } from './components/AnomalyPanel/AnomalyPanel'
import { CloudTrailSearchBar } from './components/FilterBar/CloudTrailSearchBar'
import { FilterBar } from './components/FilterBar/FilterBar'
import { LogViewer } from './components/LogViewer/LogViewer'
import { SourceSelector } from './components/SourceSelector/SourceSelector'
import { TimeRangePicker } from './components/TimeRangePicker/TimeRangePicker'
import { useSelectionStore } from './state/selectionStore'
import './App.css'

function App() {
  const events = useSelectionStore((s) => s.events)
  const sourceDescription = useSelectionStore((s) => s.sourceDescription)

  return (
    <div className="app-layout">
      <header className="app-header">
        <span className="logo-dot" />
        <h1></h1>
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
          <LogViewer />
        </main>
        <aside className="anomaly-sidebar">
          <AnomalyPanel />
        </aside>
      </div>
    </div>
  )
}

export default App
