import axios, { isAxiosError } from 'axios'
import { useEffect, useRef, useState } from 'react'

import type { AnalysisResponse, LogEvent } from '../../api/types'
import { useAnomalyAnalysis } from '../../hooks/useAnomalyAnalysis'
import { useSelectionStore } from '../../state/selectionStore'
import { AnalysisResult } from './AnalysisResult'

function errorMessage(error: unknown) {
  if (isAxiosError(error) && error.response?.status === 429) {
    return 'The AI service is busy. Wait a moment or choose a shorter time range, then try again.'
  }
  if (isAxiosError<{ detail?: unknown }>(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
  }
  return 'Check the model settings and connection, then try again.'
}

interface LogSummaryProps {
  events: LogEvent[]
}

export function LogSummary({ events }: LogSummaryProps) {
  const loadedEventCount = useSelectionStore((state) => state.events.length)
  const llmProvider = useSelectionStore((state) => state.llmProvider)
  const llmApiKey = useSelectionStore((state) => state.llmApiKey)
  const llmModel = useSelectionStore((state) => state.llmModel)
  const llmBaseUrl = useSelectionStore((state) => state.llmBaseUrl)
  const analysis = useAnomalyAnalysis()
  const abortControllerRef = useRef<AbortController | null>(null)
  const [summary, setSummary] = useState<AnalysisResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const hasListedLogs = events.length > 0
  const isPartial = summary !== null && (
    summary.lines_analyzed < summary.lines_submitted || summary.lines_shortened > 0
  )
  const hasNoAnalysis = summary !== null && summary.chunks_analyzed === 0
  const hasNoCompletedChunks = summary !== null && summary.chunks_total > 0 && summary.chunks_analyzed === 0
  const availabilityText = hasListedLogs
    ? `${events.length.toLocaleString()} visible logs ready for a one-sentence summary.`
    : loadedEventCount > 0
      ? 'No logs match the current Log details filters.'
      : 'Load logs to enable summary generation.'

  useEffect(() => {
    abortControllerRef.current?.abort()
    abortControllerRef.current = null
    setSummary(null)
    setError(null)
  }, [events, llmApiKey, llmBaseUrl, llmModel, llmProvider])

  useEffect(() => () => abortControllerRef.current?.abort(), [])

  function generateSummary() {
    if (!hasListedLogs || analysis.isPending) return

    const controller = new AbortController()
    abortControllerRef.current = controller
    setError(null)

    analysis.mutate(
      { events, userPrompt: '', history: [], signal: controller.signal },
      {
        onSuccess: (data) => setSummary(data),
        onError: (requestError) => {
          if (!axios.isCancel(requestError)) setError(errorMessage(requestError))
        },
        onSettled: () => {
          if (abortControllerRef.current === controller) abortControllerRef.current = null
        },
      },
    )
  }

  function stopSummary() {
    abortControllerRef.current?.abort()
  }

  return (
    <section className='log-summary' aria-labelledby='log-summary-title'>
      <div className='log-summary-header'>
        <div className='log-summary-heading'>
          <span className='log-summary-spark' aria-hidden='true'>✦</span>
          <div>
            <h2 id='log-summary-title'>AI Log Summary</h2>
            <p>{availabilityText}</p>
          </div>
        </div>
        <div className='log-summary-actions'>
          {analysis.isPending ? (
            <button type='button' className='log-summary-stop' onClick={stopSummary}>
              <span className='log-summary-stop-icon' aria-hidden='true' />
              Stop
            </button>
          ) : (
            <button
              type='button'
              className='btn-primary'
              disabled={!hasListedLogs}
              title={hasListedLogs ? undefined : 'Load logs before generating a summary'}
              onClick={generateSummary}
            >
              {summary ? 'Regenerate summary' : 'Generate summary'}
            </button>
          )}
        </div>
      </div>

      {(analysis.isPending || error || summary) && (
        <div className='log-summary-body'>
        {analysis.isPending ? (
          <div className='log-summary-loading' role='status' aria-live='polite'>
            <span className='spinner dark' />
            <div>
              <strong>Creating a summary from {events.length.toLocaleString()} logs</strong>
              <span>This may take a moment.</span>
            </div>
          </div>
        ) : error ? (
          <div className='log-summary-error' role='alert'>
            <div>
              <strong>We couldn’t create the summary</strong>
              <span>{error}</span>
            </div>
            <button type='button' onClick={generateSummary}>Try again</button>
          </div>
        ) : summary ? (
          <>
            <div className='log-summary-result-status' role='status' aria-live='polite'>
              {hasNoAnalysis ? (
                <span className='log-summary-no-analysis-badge'>No summary</span>
              ) : isPartial ? (
                <span className='log-summary-partial-badge'>Partial summary</span>
              ) : (
                <span className='log-summary-complete-badge'>Summary ready</span>
              )}
              <span>
                {hasNoAnalysis
                  ? `None of the ${summary.lines_submitted.toLocaleString()} selected logs were analyzed.`
                  : isPartial
                    ? `${summary.lines_analyzed.toLocaleString()} of ${summary.lines_submitted.toLocaleString()} selected logs were analyzed.`
                    : `${summary.lines_analyzed.toLocaleString()} selected logs were analyzed.`}
              </span>
            </div>
            {hasNoCompletedChunks ? (
              <div className='log-summary-insufficient' role='alert'>
                <strong>No summary was created.</strong>
                <span>Check the notes below and your model connection, then try again.</span>
              </div>
            ) : summary.chunks_total === 0 ? (
              <div className='log-summary-insufficient'>
                <strong>There weren’t enough relevant logs to summarize.</strong>
                <span>Try a wider time range or fewer filters.</span>
              </div>
            ) : (
              <AnalysisResult
                text={summary.analysis.trim() || 'The model returned no summary text for the completed chunks.'}
                className='log-summary-result'
              />
            )}
            {summary.warnings.length > 0 && (
              <div className='log-summary-warnings' role='status' aria-live='polite'>
                <strong>Important notes</strong>
                {summary.warnings.map((warning, index) => (
                  <p key={index} className='warning-text'>{warning}</p>
                ))}
              </div>
            )}
            <details className='log-summary-details'>
              <summary>How this summary was created</summary>
              <dl>
                <div><dt>Logs loaded</dt><dd>{loadedEventCount.toLocaleString()}</dd></div>
                <div><dt>Logs selected</dt><dd>{summary.lines_submitted.toLocaleString()}</dd></div>
                <div><dt>Logs analyzed</dt><dd>{summary.lines_analyzed.toLocaleString()}</dd></div>
                <div><dt>Filtered or sampled out</dt><dd>{summary.lines_skipped_by_prefilter.toLocaleString()}</dd></div>
                <div><dt>Excluded by processing limits</dt><dd>{summary.lines_omitted_by_limits.toLocaleString()}</dd></div>
                <div><dt>Not completed</dt><dd>{summary.lines_not_analyzed.toLocaleString()}</dd></div>
                <div><dt>Shortened</dt><dd>{summary.lines_shortened.toLocaleString()}</dd></div>
                <div><dt>Processing batches</dt><dd>{summary.chunks_analyzed}/{summary.chunks_total}</dd></div>
              </dl>
            </details>
            <p className='log-summary-disclaimer'>
              AI summaries can miss details. Select a cited line number to check the supporting log.
            </p>
          </>
        ) : null}
        </div>
      )}
    </section>
  )
}
