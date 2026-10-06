import { beforeEach, describe, expect, it } from 'vitest'

import type { LogEvent } from '../api/types'
import { MAX_LIVE_TAIL_EVENTS, useSelectionStore } from './selectionStore'

const initialState = useSelectionStore.getState()
const event = (message: string): LogEvent => ({
  source: 'cloudwatch', origin: 'group', stream_or_key: 'stream',
  timestamp: '2026-01-01T00:00:00Z', message, line_index: 0,
})

beforeEach(() => useSelectionStore.setState(initialState, true))

describe('selection state', () => {
  it('keeps credentials and endpoints isolated by provider', () => {
    let state = useSelectionStore.getState()
    state.setLlmApiKey('lite-key')
    state.setLlmModel('lite-model')
    state.setLlmBaseUrl('https://proxy.example/v1')
    state.setLlmProvider('openai')

    state = useSelectionStore.getState()
    expect([state.llmApiKey, state.llmModel, state.llmBaseUrl]).toEqual(['', '', ''])
    state.setLlmApiKey('openai-key')
    state.setLlmProvider('litellm')

    state = useSelectionStore.getState()
    expect([state.llmApiKey, state.llmModel, state.llmBaseUrl]).toEqual([
      'lite-key', 'lite-model', 'https://proxy.example/v1',
    ])
    state.setLlmProvider('openai')
    expect(useSelectionStore.getState().llmApiKey).toBe('openai-key')
  })

  it('invalidates responses from older searches and source modes', () => {
    const first = useSelectionStore.getState().beginSearch('cloudwatch')
    expect(useSelectionStore.getState().isCurrentSearch(first, 'cloudwatch')).toBe(true)
    useSelectionStore.getState().setEvents([event('old source')], 'CloudWatch')
    useSelectionStore.getState().setSourceMode('cloudtrail')
    expect(useSelectionStore.getState().isCurrentSearch(first, 'cloudwatch')).toBe(false)
    expect(useSelectionStore.getState().events).toEqual([])

    const second = useSelectionStore.getState().beginSearch('cloudtrail')
    useSelectionStore.getState().invalidateSearch()
    expect(useSelectionStore.getState().isCurrentSearch(second, 'cloudtrail')).toBe(false)

    useSelectionStore.getState().startSearchRequest()
    useSelectionStore.getState().startSearchRequest()
    expect(useSelectionStore.getState().searchInFlightCount).toBe(2)
    useSelectionStore.getState().finishSearchRequest()
    expect(useSelectionStore.getState().searchInFlightCount).toBe(1)
  })

  it('assigns unique indices to every appended event and bounds live history', () => {
    useSelectionStore.getState().setEvents([event('first')], 'search')
    useSelectionStore.getState().appendEvents([event('second'), event('third')])
    expect(useSelectionStore.getState().events.map((item) => item.line_index)).toEqual([0, 1, 2])

    useSelectionStore.getState().setEvents([], 'Live Tail')
    const batch = Array.from({ length: MAX_LIVE_TAIL_EVENTS + 2 }, (_, index) => event(String(index)))
    useSelectionStore.getState().appendLiveEvents(batch)
    let state = useSelectionStore.getState()
    expect(state.events).toHaveLength(MAX_LIVE_TAIL_EVENTS)
    expect([state.events[0].line_index, state.events[state.events.length - 1]?.line_index]).toEqual([2, MAX_LIVE_TAIL_EVENTS + 1])
    expect(state.liveTailDroppedEvents).toBe(2)

    state.appendLiveEvents([event('later'), event('latest')])
    state = useSelectionStore.getState()
    expect(state.events[state.events.length - 1]?.line_index).toBe(MAX_LIVE_TAIL_EVENTS + 3)
    expect(state.liveTailDroppedEvents).toBe(4)
  })
})
