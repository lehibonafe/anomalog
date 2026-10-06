import { useEffect, useRef, useState, type MouseEvent } from 'react'

import { cloudWatchLiveTailUrl, fetchAppConfig } from '../../api/cloudwatch'
import type { LiveTailServerMessage, LogEvent } from '../../api/types'
import { useSelectionStore } from '../../state/selectionStore'

type LiveTailStatus = 'idle' | 'connecting' | 'active' | 'paused' | 'stopping'

const PAUSED_EVENT_BUFFER_LIMIT = 5000

interface LiveTailControlsProps {
  onRunningChange: (running: boolean) => void
}

function formatElapsed(seconds: number) {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const remainingSeconds = seconds % 60
  return hours > 0
    ? `${hours}:${String(minutes).padStart(2, '0')}:${String(remainingSeconds).padStart(2, '0')}`
    : `${minutes}:${String(remainingSeconds).padStart(2, '0')}`
}

export function LiveTailControls({ onRunningChange }: LiveTailControlsProps) {
  const logGroupNames = useSelectionStore((state) => state.logGroupNames)
  const filterPattern = useSelectionStore((state) => state.filterPattern)
  const sourceDescription = useSelectionStore((state) => state.sourceDescription)
  const setEvents = useSelectionStore((state) => state.setEvents)
  const appendLiveEvents = useSelectionStore((state) => state.appendLiveEvents)
  const invalidateSearch = useSelectionStore((state) => state.invalidateSearch)
  const droppedLiveEvents = useSelectionStore((state) => state.liveTailDroppedEvents)
  const searchInFlightCount = useSelectionStore((state) => state.searchInFlightCount)
  const socketRef = useRef<WebSocket | null>(null)
  const confirmationRef = useRef<HTMLDialogElement | null>(null)
  const startedAtRef = useRef<number | null>(null)
  const pausedRef = useRef(false)
  const pausedEventsRef = useRef<LogEvent[]>([])
  const [status, setStatus] = useState<LiveTailStatus>('idle')
  const [showConfirmation, setShowConfirmation] = useState(false)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const [eventCount, setEventCount] = useState(0)
  const [costPerMinute, setCostPerMinute] = useState(0.01)
  const [freeTierMinutes, setFreeTierMinutes] = useState(1800)
  const [inactivitySeconds, setInactivitySeconds] = useState(900)
  const [error, setError] = useState<string | null>(null)
  const [stopReason, setStopReason] = useState<string | null>(null)
  const [isSampled, setIsSampled] = useState(false)
  const [bufferedEventCount, setBufferedEventCount] = useState(0)
  const [droppedPausedEventCount, setDroppedPausedEventCount] = useState(0)

  const running = status !== 'idle'
  const showingLiveHistory = sourceDescription.startsWith('CloudWatch Live Tail:')
  const selectionIsValid = logGroupNames.length > 0 && logGroupNames.length <= 10
  const billedMinutes = elapsedSeconds === 0 ? 0 : Math.ceil(elapsedSeconds / 60)
  const estimatedCost = billedMinutes * costPerMinute

  useEffect(() => onRunningChange(running), [onRunningChange, running])

  useEffect(() => {
    void fetchAppConfig().then((config) => {
      setInactivitySeconds(config.live_tail_inactivity_timeout_seconds)
      setCostPerMinute(config.live_tail_cost_per_minute_usd)
      setFreeTierMinutes(config.live_tail_free_tier_minutes)
    }).catch(() => {
      // Keep the published AWS/default safety values when config is unavailable.
    })
  }, [])

  useEffect(() => {
    const dialog = confirmationRef.current
    if (!dialog) return
    if (showConfirmation && !dialog.open) dialog.showModal()
    else if (!showConfirmation && dialog.open) dialog.close()
  }, [showConfirmation])

  useEffect(() => {
    if (status === 'idle' || startedAtRef.current === null) return
    const updateElapsed = () => setElapsedSeconds(
      Math.floor((Date.now() - startedAtRef.current!) / 1000),
    )
    updateElapsed()
    const timer = window.setInterval(updateElapsed, 1000)
    return () => window.clearInterval(timer)
  }, [status])

  useEffect(() => {
    if (status !== 'active' && status !== 'paused') return
    let lastActivitySent = 0
    const recordActivity = () => {
      const socket = socketRef.current
      const now = Date.now()
      if (socket?.readyState === WebSocket.OPEN && now - lastActivitySent >= 30_000) {
        socket.send(JSON.stringify({ type: 'activity' }))
        lastActivitySent = now
      }
    }
    const events: Array<keyof WindowEventMap> = ['pointerdown', 'keydown', 'scroll', 'touchstart']
    events.forEach((name) => window.addEventListener(name, recordActivity, { passive: true }))
    return () => events.forEach((name) => window.removeEventListener(name, recordActivity))
  }, [status])

  useEffect(() => {
    const closeSocket = () => socketRef.current?.close()
    window.addEventListener('beforeunload', closeSocket)
    return () => {
      window.removeEventListener('beforeunload', closeSocket)
      const socket = socketRef.current
      if (socket) {
        socket.onopen = null
        socket.onmessage = null
        socket.onerror = null
        socket.onclose = null
        socket.close()
        socketRef.current = null
      }
      pausedEventsRef.current = []
    }
  }, [])

  function closeConfirmation() {
    setShowConfirmation(false)
  }

  function closeConfirmationFromBackdrop(event: MouseEvent<HTMLDialogElement>) {
    const bounds = event.currentTarget.getBoundingClientRect()
    const isOutside = event.clientX < bounds.left
      || event.clientX > bounds.right
      || event.clientY < bounds.top
      || event.clientY > bounds.bottom
    if (isOutside) closeConfirmation()
  }

  function startLiveTail() {
    if (!selectionIsValid || running || useSelectionStore.getState().searchInFlightCount > 0) return
    closeConfirmation()
    setStatus('connecting')
    setError(null)
    setStopReason(null)
    setEventCount(0)
    setElapsedSeconds(0)
    setIsSampled(false)
    setBufferedEventCount(0)
    setDroppedPausedEventCount(0)
    startedAtRef.current = null
    pausedRef.current = false
    pausedEventsRef.current = []

    const selectedGroups = [...logGroupNames]
    const selectedFilter = filterPattern.trim() || null
    const socket = new WebSocket(cloudWatchLiveTailUrl())
    socketRef.current = socket

    socket.onopen = () => socket.send(JSON.stringify({
      type: 'start',
      log_group_names: selectedGroups,
      filter_pattern: selectedFilter,
    }))

    socket.onmessage = (event) => {
      if (useSelectionStore.getState().sourceMode !== 'cloudwatch') {
        socket.close()
        return
      }
      const message = JSON.parse(event.data) as LiveTailServerMessage
      if (message.type === 'session_started') {
        setInactivitySeconds(message.inactivity_timeout_seconds)
        setCostPerMinute(message.cost_per_minute_usd)
        setFreeTierMinutes(message.free_tier_minutes)
        invalidateSearch()
        setEvents([], `CloudWatch Live Tail: ${selectedGroups.join(', ')}`)
        startedAtRef.current = Date.now()
        setStatus('active')
      } else if (message.type === 'events') {
        setEventCount((count) => count + message.events.length)
        if (pausedRef.current) {
          const combined = [...pausedEventsRef.current, ...message.events]
          const overflow = Math.max(0, combined.length - PAUSED_EVENT_BUFFER_LIMIT)
          pausedEventsRef.current = overflow > 0 ? combined.slice(overflow) : combined
          setBufferedEventCount(pausedEventsRef.current.length)
          if (overflow > 0) {
            setDroppedPausedEventCount((count) => count + overflow)
          }
        } else {
          appendLiveEvents(message.events)
        }
        if (message.sampled) setIsSampled(true)
      } else if (message.type === 'error') {
        setError(message.message)
        socket.close()
      } else {
        setStopReason(message.reason)
        socket.close()
      }
    }

    socket.onerror = () => {
      setError((current) => current ?? 'Could not connect to CloudWatch Live Tail.')
    }

    socket.onclose = () => {
      if (socketRef.current === socket) socketRef.current = null
      if (useSelectionStore.getState().sourceMode === 'cloudwatch') flushPausedEvents()
      pausedRef.current = false
      setStatus('idle')
    }
  }

  function flushPausedEvents() {
    if (pausedEventsRef.current.length > 0) {
      appendLiveEvents(pausedEventsRef.current)
      pausedEventsRef.current = []
    }
    setBufferedEventCount(0)
  }

  function pauseLiveTail() {
    if (status !== 'active') return
    pausedRef.current = true
    setStatus('paused')
  }

  function resumeLiveTail() {
    if (status !== 'paused') return
    pausedRef.current = false
    flushPausedEvents()
    setStatus('active')
  }

  function stopLiveTail() {
    const socket = socketRef.current
    if (!socket) return
    pausedRef.current = false
    flushPausedEvents()
    setStatus('stopping')
    if (socket.readyState === WebSocket.OPEN) {
      socket.send(JSON.stringify({ type: 'stop' }))
      window.setTimeout(() => {
        if (socket.readyState !== WebSocket.CLOSED) socket.close()
      }, 2000)
    } else {
      socket.close()
    }
  }

  return (
    <div className='live-tail-controls'>
      <div className='panel-section-title'>Live Tail</div>
      {running ? (
        <div className='live-tail-session' role='status' aria-live='polite'>
          <div className='live-tail-session-heading'>
            <span className={`live-tail-indicator${status === 'active' ? ' active' : status === 'paused' ? ' paused' : ''}`} />
            <strong>{status === 'connecting' ? 'Connecting…' : status === 'stopping' ? 'Stopping…' : status === 'paused' ? 'Live Tail paused' : 'Live Tail active'}</strong>
          </div>
          <dl>
            <div><dt>Session</dt><dd>{formatElapsed(elapsedSeconds)}</dd></div>
            <div><dt>Events</dt><dd>{eventCount.toLocaleString()}</dd></div>
            <div><dt>Estimated cost</dt><dd>${estimatedCost.toFixed(2)}</dd></div>
          </dl>
          <p className='hint'>Before the AWS free tier. Stops after {Math.round(inactivitySeconds / 60)} minutes without activity.</p>
          {status === 'paused' && (
            <p className='warning-text'>Display paused with {bufferedEventCount.toLocaleString()} event{bufferedEventCount === 1 ? '' : 's'} buffered. The AWS session remains active and billable.</p>
          )}
          {isSampled && <p className='warning-text'>AWS is sampling this high-volume stream.</p>}
          <div className='live-tail-session-actions'>
            <button
              type='button'
              className='btn-block'
              disabled={status === 'connecting' || status === 'stopping'}
              onClick={status === 'paused' ? resumeLiveTail : pauseLiveTail}
            >
              {status === 'paused' ? `Resume (${bufferedEventCount.toLocaleString()})` : 'Pause display'}
            </button>
            <button type='button' className='btn-block live-tail-stop' disabled={status === 'stopping'} onClick={stopLiveTail}>Stop Live Tail</button>
          </div>
        </div>
      ) : (
        <>
          <button type='button' className='btn-block' disabled={!selectionIsValid || searchInFlightCount > 0} onClick={() => setShowConfirmation(true)}>Start Live Tail</button>
          <p className='hint'>Starts only after confirmation. Maximum {freeTierMinutes.toLocaleString()} free AWS minutes per month, then ${costPerMinute.toFixed(2)}/minute.</p>
          {logGroupNames.length > 10 && <p className='error-text'>Live Tail supports up to 10 selected log groups.</p>}
        </>
      )}
      {showingLiveHistory && droppedPausedEventCount > 0 && (
        <p className='warning-text'>{droppedPausedEventCount.toLocaleString()} older paused event{droppedPausedEventCount === 1 ? '' : 's'} discarded after the {PAUSED_EVENT_BUFFER_LIMIT.toLocaleString()}-event buffer filled.</p>
      )}
      {showingLiveHistory && droppedLiveEvents > 0 && (
        <p className='warning-text'>{droppedLiveEvents.toLocaleString()} older event{droppedLiveEvents === 1 ? '' : 's'} removed from the displayed Live Tail history.</p>
      )}
      {error && <p className='error-text' role='alert'>{error}</p>}
      {stopReason && !running && showingLiveHistory && <p className='hint' role='status'>{stopReason}</p>}

      <dialog
        ref={confirmationRef}
        className='live-tail-confirmation'
        aria-labelledby='live-tail-confirmation-title'
        onCancel={closeConfirmation}
        onClose={closeConfirmation}
        onClick={closeConfirmationFromBackdrop}
      >
        <h2 id='live-tail-confirmation-title'>Start CloudWatch Live Tail?</h2>
        <p>This starts a billable AWS session for {logGroupNames.length} log group{logGroupNames.length === 1 ? '' : 's'} and replaces the currently displayed logs with live events.</p>
        <ul>
          <li>AWS includes {freeTierMinutes.toLocaleString()} Live Tail minutes per month, then charges ${costPerMinute.toFixed(2)} per minute.</li>
          <li>The session stops after {Math.round(inactivitySeconds / 60)} minutes without activity.</li>
          <li>Closing or leaving this page stops the session.</li>
        </ul>
        <div className='live-tail-confirmation-actions'>
          <button type='button' onClick={closeConfirmation}>Cancel</button>
          <button type='button' className='btn-primary' disabled={searchInFlightCount > 0} onClick={startLiveTail}>Start Live Tail</button>
        </div>
      </dialog>
    </div>
  )
}
