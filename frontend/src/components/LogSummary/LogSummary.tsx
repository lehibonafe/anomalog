import axios, { isAxiosError } from 'axios'
import { type FormEvent, useEffect, useRef, useState } from 'react'

import type { AnalysisResponse, ChatMessage, LogEvent } from '../../api/types'
import { useAnomalyAnalysis } from '../../hooks/useAnomalyAnalysis'
import { useSelectionStore } from '../../state/selectionStore'
import { modelDestination } from '../../utils/modelDestination'
import { AnalysisResult } from './AnalysisResult'

const INVESTIGATION_HISTORY_KEY = 'anomalog.investigation-history.v1'
const MAX_SAVED_INVESTIGATIONS = 20

const CLOUDWATCH_QUESTIONS = [
  'What errors are repeating, and which service is most affected?',
  'What happened immediately before the first failure?',
  'Are timeouts, retries, or dependency failures causing the issue?',
]

const CLOUDTRAIL_QUESTIONS = [
  'Who made the highest-impact changes, and from which IP?',
  'Which resources were created, changed, or deleted?',
  'Are there access denials or suspicious IAM activities?',
]

function GenerateIcon() {
  return (
    <svg className='log-investigator-generate-icon' viewBox='0 0 20 20' aria-hidden='true'>
      <path d='M8.5 2.5c.35 3.2 2.1 4.95 5.3 5.3-3.2.35-4.95 2.1-5.3 5.3-.35-3.2-2.1-4.95-5.3-5.3 3.2-.35 4.95-2.1 5.3-5.3Z' />
      <path d='M15.5 12.5c.15 1.5 1 2.35 2.5 2.5-1.5.15-2.35 1-2.5 2.5-.15-1.5-1-2.35-2.5-2.5 1.5-.15 2.35-1 2.5-2.5Z' />
    </svg>
  )
}

interface InvestigationTurn {
  id: number
  question: string
  response: AnalysisResponse
}

interface SavedInvestigation {
  id: string
  source: string
  startTime: string
  endTime: string
  updatedAt: string
  turns: InvestigationTurn[]
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null
}

function isSavedInvestigation(value: unknown): value is SavedInvestigation {
  if (!isRecord(value) || !Array.isArray(value.turns)) return false

  return typeof value.id === 'string'
    && typeof value.source === 'string'
    && typeof value.startTime === 'string'
    && typeof value.endTime === 'string'
    && typeof value.updatedAt === 'string'
    && value.turns.length > 0
    && value.turns.every((turn) => (
      isRecord(turn)
      && typeof turn.id === 'number'
      && typeof turn.question === 'string'
      && isRecord(turn.response)
      && typeof turn.response.analysis === 'string'
      && typeof turn.response.chunks_analyzed === 'number'
      && typeof turn.response.chunks_total === 'number'
      && typeof turn.response.lines_submitted === 'number'
      && typeof turn.response.lines_analyzed === 'number'
      && typeof turn.response.lines_shortened === 'number'
      && Array.isArray(turn.response.warnings)
      && turn.response.warnings.every((warning) => typeof warning === 'string')
    ))
}

function loadInvestigationHistory(): SavedInvestigation[] {
  try {
    const stored = window.localStorage.getItem(INVESTIGATION_HISTORY_KEY)
    if (!stored) return []
    const parsed: unknown = JSON.parse(stored)
    return Array.isArray(parsed) ? parsed.filter(isSavedInvestigation) : []
  } catch {
    return []
  }
}

function persistInvestigationHistory(investigations: SavedInvestigation[]) {
  try {
    window.localStorage.setItem(INVESTIGATION_HISTORY_KEY, JSON.stringify(investigations))
  } catch {
    // History is a convenience; the active chat should still work if storage is unavailable.
  }
}

function investigationId() {
  return typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`
}

function formatTimeRange(startTime: string, endTime: string) {
  const start = new Date(startTime)
  const end = new Date(endTime)
  if (!startTime || !endTime || Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
    return 'Time range unavailable'
  }

  const date = new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' })
  const time = new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' })
  const sameDay = start.toDateString() === end.toDateString()
  return sameDay
    ? `${date.format(start)}, ${time.format(start)} – ${time.format(end)}`
    : `${date.format(start)}, ${time.format(start)} – ${date.format(end)}, ${time.format(end)}`
}

function errorMessage(error: unknown) {
  if (isAxiosError(error) && error.response?.status === 429) {
    return 'The AI service is busy. Wait a moment and try again.'
  }
  if (isAxiosError<{ detail?: unknown }>(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
  }
  return 'Check the model settings and connection, then try again.'
}

function conversationHistory(turns: InvestigationTurn[]): ChatMessage[] {
  return turns.flatMap<ChatMessage>((turn) => [
    { role: 'user', content: turn.question },
    { role: 'assistant', content: turn.response.analysis },
  ]).slice(-40)
}

function InvestigationAnswer({ response }: { response: AnalysisResponse }) {
  const isPartial = response.lines_analyzed < response.lines_submitted || response.lines_shortened > 0
  const hasAnswer = response.chunks_analyzed > 0 && response.chunks_total > 0
  const linesSentToModel = response.lines_sent_to_model ?? response.lines_analyzed
  const collapsedLines = response.lines_collapsed_as_duplicates ?? 0
  const estimatedInputTokens = response.estimated_input_tokens ?? 0
  const hasNotes = isPartial || collapsedLines > 0 || response.warnings.length > 0

  return (
    <div className='log-investigator-answer'>
      {hasAnswer ? (
        <AnalysisResult
          text={response.analysis.trim() || 'The model returned no answer.'}
          className='log-summary-result'
        />
      ) : (
        <p className='log-investigator-empty-answer'>No answer could be created from these logs.</p>
      )}

      {hasNotes && (
        <details className='log-investigator-notes'>
          <summary>Analysis notes</summary>
          {isPartial && (
            <p>
              Analyzed {response.lines_analyzed.toLocaleString()} of{' '}
              {response.lines_submitted.toLocaleString()} visible logs.
            </p>
          )}
          {collapsedLines > 0 && (
            <p>
              Represented repetitive logs with {linesSentToModel.toLocaleString()} compact evidence rows.
            </p>
          )}
          {estimatedInputTokens > 0 && (
            <p>Estimated model input: {estimatedInputTokens.toLocaleString()} tokens.</p>
          )}
          {response.warnings.map((warning, index) => <p key={index}>{warning}</p>)}
        </details>
      )}
    </div>
  )
}

interface InvestigationConversationProps {
  turns: InvestigationTurn[]
  pendingQuestion: string | null
  error: string | null
  failedQuestion: string | null
  onRetry: (question: string) => void
}

function InvestigationConversation({
  turns,
  pendingQuestion,
  error,
  failedQuestion,
  onRetry,
}: InvestigationConversationProps) {
  return (
    <>
      {turns.map((turn) => (
        <article className='log-investigator-turn' key={turn.id}>
          <p className='log-investigator-question'>{turn.question}</p>
          <InvestigationAnswer response={turn.response} />
        </article>
      ))}

      {pendingQuestion && (
        <div className='log-investigator-pending' role='status'>
          <p className='log-investigator-question'>{pendingQuestion}</p>
          <span className='spinner dark' />
          <span>Investigating…</span>
        </div>
      )}

      {error && failedQuestion && (
        <div className='log-investigator-failure'>
          <p className='log-investigator-question'>{failedQuestion}</p>
          <div className='log-summary-error' role='alert'>
            <span>{error}</span>
            <button type='button' onClick={() => onRetry(failedQuestion)}>Retry</button>
          </div>
        </div>
      )}
    </>
  )
}

interface LogSummaryProps {
  events: LogEvent[]
}

export function LogSummary({ events }: LogSummaryProps) {
  const loadedEventCount = useSelectionStore((state) => state.events.length)
  const sourceMode = useSelectionStore((state) => state.sourceMode)
  const startTime = useSelectionStore((state) => state.startTime)
  const endTime = useSelectionStore((state) => state.endTime)
  const llmProvider = useSelectionStore((state) => state.llmProvider)
  const llmApiKey = useSelectionStore((state) => state.llmApiKey)
  const llmModel = useSelectionStore((state) => state.llmModel)
  const llmBaseUrl = useSelectionStore((state) => state.llmBaseUrl)
  const analysis = useAnomalyAnalysis()
  const abortControllerRef = useRef<AbortController | null>(null)
  const compactConversationRef = useRef<HTMLDivElement | null>(null)
  const expandedConversationRef = useRef<HTMLDivElement | null>(null)
  const chatDialogRef = useRef<HTMLDialogElement | null>(null)
  const [turns, setTurns] = useState<InvestigationTurn[]>([])
  const [savedInvestigations, setSavedInvestigations] = useState(loadInvestigationHistory)
  const [activeInvestigationId, setActiveInvestigationId] = useState<string | null>(null)
  const [historyDrawerOpen, setHistoryDrawerOpen] = useState(false)
  const [question, setQuestion] = useState('')
  const [pendingQuestion, setPendingQuestion] = useState<string | null>(null)
  const [failedQuestion, setFailedQuestion] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const hasVisibleLogs = events.length > 0
  const suggestedQuestions = sourceMode === 'cloudtrail'
    ? CLOUDTRAIL_QUESTIONS
    : CLOUDWATCH_QUESTIONS
  const availabilityText = hasVisibleLogs
    ? `${events.length.toLocaleString()} visible logs`
    : loadedEventCount > 0
      ? 'No logs match the current filters'
      : 'Load logs to ask a question'
  const hasConversation = turns.length > 0 || pendingQuestion !== null || error !== null
  const canOpenChat = hasConversation || savedInvestigations.length > 0

  useEffect(() => {
    abortControllerRef.current?.abort()
    abortControllerRef.current = null
    setTurns([])
    setActiveInvestigationId(null)
    setPendingQuestion(null)
    setFailedQuestion(null)
    setError(null)
  }, [events, llmApiKey, llmBaseUrl, llmModel, llmProvider])

  useEffect(() => () => abortControllerRef.current?.abort(), [])

  useEffect(() => {
    for (const conversation of [compactConversationRef.current, expandedConversationRef.current]) {
      if (conversation) conversation.scrollTop = conversation.scrollHeight
    }
  }, [turns, pendingQuestion, error])

  function askQuestion(questionToAsk: string) {
    const trimmedQuestion = questionToAsk.trim()
    if (!hasVisibleLogs || !trimmedQuestion || abortControllerRef.current) return

    const controller = new AbortController()
    abortControllerRef.current = controller
    setQuestion('')
    setPendingQuestion(trimmedQuestion)
    setFailedQuestion(null)
    setError(null)

    analysis.mutate(
      {
        events,
        userPrompt: trimmedQuestion,
        history: conversationHistory(turns),
        signal: controller.signal,
      },
      {
        onSuccess: (response) => {
          const nextTurns = [
            ...turns,
            {
              id: turns.reduce((largest, turn) => Math.max(largest, turn.id), -1) + 1,
              question: trimmedQuestion,
              response,
            },
          ]
          const id = activeInvestigationId ?? investigationId()
          const existingInvestigation = savedInvestigations.find((item) => item.id === id)
          const currentSource = events[0]?.source === 'cloudtrail'
            ? 'CloudTrail'
            : events[0]?.source === 'cloudwatch'
              ? 'CloudWatch'
              : sourceMode === 'cloudtrail' ? 'CloudTrail' : 'CloudWatch'
          const saved: SavedInvestigation = {
            id,
            source: existingInvestigation?.source ?? currentSource,
            startTime: existingInvestigation?.startTime ?? startTime,
            endTime: existingInvestigation?.endTime ?? endTime,
            updatedAt: new Date().toISOString(),
            turns: nextTurns,
          }

          setTurns(nextTurns)
          setActiveInvestigationId(id)
          setSavedInvestigations((current) => {
            const next = [saved, ...current.filter((item) => item.id !== id)]
              .slice(0, MAX_SAVED_INVESTIGATIONS)
            persistInvestigationHistory(next)
            return next
          })
        },
        onError: (requestError) => {
          if (axios.isCancel(requestError)) return
          setFailedQuestion(trimmedQuestion)
          setError(errorMessage(requestError))
        },
        onSettled: () => {
          if (abortControllerRef.current === controller) abortControllerRef.current = null
          setPendingQuestion(null)
        },
      },
    )
  }

  function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    askQuestion(question)
  }

  function stopInvestigation() {
    if (pendingQuestion) setQuestion(pendingQuestion)
    abortControllerRef.current?.abort()
  }

  function clearInvestigation() {
    chatDialogRef.current?.close()
    startNewInvestigation()
  }

  function startNewInvestigation() {
    if (analysis.isPending) return
    setTurns([])
    setActiveInvestigationId(null)
    setQuestion('')
    setFailedQuestion(null)
    setError(null)
    setHistoryDrawerOpen(false)
  }

  function restoreInvestigation(investigation: SavedInvestigation) {
    if (analysis.isPending) return
    setTurns(investigation.turns)
    setActiveInvestigationId(investigation.id)
    setQuestion('')
    setFailedQuestion(null)
    setError(null)
    setHistoryDrawerOpen(false)
  }

  function deleteInvestigation() {
    if (!activeInvestigationId || analysis.isPending) return
    setSavedInvestigations((current) => {
      const next = current.filter((item) => item.id !== activeInvestigationId)
      persistInvestigationHistory(next)
      return next
    })
    startNewInvestigation()
  }

  function openChat() {
    setHistoryDrawerOpen(false)
    chatDialogRef.current?.showModal()
  }

  return (
    <section className='log-summary log-investigator' aria-labelledby='log-investigator-title'>
      <div className='log-summary-header'>
        <div className='log-summary-heading'>
          <span className='log-summary-spark' aria-hidden='true'>✦</span>
          <div>
            <h2 id='log-investigator-title'>AI Log Investigator</h2>
            <p>{availabilityText}</p>
            <p>AI destination: {modelDestination(llmProvider, llmBaseUrl)}</p>
          </div>
        </div>
        {canOpenChat && (
          <div className='log-investigator-header-actions'>
            <button type='button' onClick={openChat}>
              <svg viewBox='0 0 20 20' aria-hidden='true'>
                <path d='M3 4.5h14v9H8l-4 3v-3H3z' />
              </svg>
              View chat
            </button>
            {hasConversation && !analysis.isPending && (
              <button type='button' className='log-investigator-clear' onClick={clearInvestigation}>
                Clear
              </button>
            )}
          </div>
        )}
      </div>

      <div className='log-summary-body'>
        <form className='log-investigator-form' onSubmit={submitQuestion}>
          <div className='log-investigator-input-row'>
            <input
              type='text'
              maxLength={1000}
              aria-label='Ask about the visible logs'
              value={question}
              disabled={!hasVisibleLogs || analysis.isPending}
              placeholder='Ask a question about these logs…'
              onChange={(event) => setQuestion(event.target.value)}
            />
            {analysis.isPending ? (
              <button type='button' onClick={stopInvestigation}>Stop</button>
            ) : (
              <button
                type='submit'
                className='btn-primary'
                disabled={!hasVisibleLogs || !question.trim()}
              >
                <GenerateIcon />
                Generate
              </button>
            )}
          </div>
        </form>

        {turns.length === 0 && !pendingQuestion && !error && (
          <div className='log-investigator-suggestions' aria-label='Suggested questions'>
            {suggestedQuestions.map((suggestion) => (
              <button
                type='button'
                key={suggestion}
                disabled={!hasVisibleLogs}
                onClick={() => setQuestion(suggestion)}
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}

        {hasConversation && (
          <div
            ref={compactConversationRef}
            className='log-investigator-conversation'
            aria-live='polite'
          >
            <InvestigationConversation
              turns={turns}
              pendingQuestion={pendingQuestion}
              error={error}
              failedQuestion={failedQuestion}
              onRetry={askQuestion}
            />
          </div>
        )}
      </div>

      <dialog
        ref={chatDialogRef}
        className='log-investigator-chat-dialog'
        aria-labelledby='log-investigator-chat-title'
        onClose={() => setHistoryDrawerOpen(false)}
        onClick={(event) => {
          if (event.target === event.currentTarget) event.currentTarget.close()
        }}
      >
        <div className='log-investigator-chat-header'>
          <div>
            <h2 id='log-investigator-chat-title'>Investigation chat</h2>
            <p>{availabilityText}</p>
          </div>
          <div className='log-investigator-chat-header-actions'>
            <button
              type='button'
              className='model-settings-dialog-close'
              aria-label='Close investigation chat'
              onClick={() => chatDialogRef.current?.close()}
            >
              ×
            </button>
          </div>
        </div>

        <div className='log-investigator-chat-layout'>
          {historyDrawerOpen && (
            <button
              type='button'
              className='log-investigator-history-scrim'
              aria-label='Close history'
              onClick={() => setHistoryDrawerOpen(false)}
            />
          )}
          <aside
            id='investigation-history'
            className={`log-investigator-history${historyDrawerOpen ? ' open' : ''}`}
            aria-label='Saved investigations'
          >
            <div className='log-investigator-history-header'>
              <strong>History</strong>
              <button
                type='button'
                className='log-investigator-history-close'
                aria-label='Close history'
                onClick={() => setHistoryDrawerOpen(false)}
              >
                ×
              </button>
            </div>
            <button
              type='button'
              className='log-investigator-new-button'
              disabled={analysis.isPending}
              onClick={startNewInvestigation}
            >
              <span aria-hidden='true'>＋</span>
              New investigation
            </button>
            <div className='log-investigator-history-list'>
              {savedInvestigations.length === 0 ? (
                <p className='log-investigator-history-empty'>Completed conversations will appear here.</p>
              ) : savedInvestigations.map((investigation) => (
                <button
                  type='button'
                  className={`log-investigator-history-entry${activeInvestigationId === investigation.id ? ' active' : ''}`}
                  key={investigation.id}
                  disabled={analysis.isPending}
                  aria-current={activeInvestigationId === investigation.id ? 'true' : undefined}
                  onClick={() => restoreInvestigation(investigation)}
                >
                  <strong>{investigation.source}</strong>
                  <span>{formatTimeRange(investigation.startTime, investigation.endTime)}</span>
                  <span className='log-investigator-history-question'>
                    {investigation.turns[investigation.turns.length - 1]?.question}
                  </span>
                </button>
              ))}
            </div>
            <button
              type='button'
              className='log-investigator-delete-button'
              disabled={!activeInvestigationId || analysis.isPending}
              onClick={deleteInvestigation}
            >
              Delete
            </button>
          </aside>

          <div className='log-investigator-chat-main'>
            <div ref={expandedConversationRef} className='log-investigator-chat-body'>
              <div className='log-investigator-conversation'>
                <InvestigationConversation
                  turns={turns}
                  pendingQuestion={pendingQuestion}
                  error={error}
                  failedQuestion={failedQuestion}
                  onRetry={askQuestion}
                />
              </div>
            </div>
            <form className='log-investigator-chat-form' onSubmit={submitQuestion}>
              <div className='log-investigator-input-row'>
                <input
                  type='text'
                  maxLength={1000}
                  aria-label='Ask a question in the investigation chat'
                  value={question}
                  disabled={!hasVisibleLogs || analysis.isPending}
                  placeholder='Ask a follow-up question…'
                  onChange={(event) => setQuestion(event.target.value)}
                />
                {analysis.isPending ? (
                  <button type='button' onClick={stopInvestigation}>Stop</button>
                ) : (
                  <button
                    type='submit'
                    className='btn-primary'
                    disabled={!hasVisibleLogs || !question.trim()}
                  >
                    <GenerateIcon />
                    Generate
                  </button>
                )}
              </div>
            </form>
          </div>
        </div>
      </dialog>
    </section>
  )
}
