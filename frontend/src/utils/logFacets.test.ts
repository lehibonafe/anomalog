import { describe, expect, it } from 'vitest'

import type { LogEvent } from '../api/types'
import {
  extractLogFacets,
  isSignificantHttpStatus,
  SIGNIFICANT_HTTP_STATUS_CODES,
} from './logFacets'

function event(message: string): LogEvent {
  return {
    source: 'cloudwatch',
    origin: 'test-group',
    stream_or_key: 'test-stream',
    timestamp: '2026-09-15T00:00:00Z',
    message,
    line_index: 0,
  }
}

describe('HTTP status extraction', () => {
  it('prefers a structured status field over unrelated numbers', () => {
    expect(extractLogFacets(event('{"status_code":503,"duration_ms":200}')).status).toBe('503')
  })

  it.each([
    ['status=429 duration=200ms', '429'],
    ['status code: 408 elapsed=500ms', '408'],
    ['HTTP/2 503 Service Unavailable', '503'],
    ['10.0.0.1 - "GET /health HTTP/1.1" 200 42', '200'],
    ['POST /jobs 202 duration=15ms', '202'],
  ])('extracts an explicit HTTP status from %s', (message, expected) => {
    expect(extractLogFacets(event(message)).status).toBe(expected)
  })

  it.each([
    'duration=200ms',
    'order 404 was delivered',
    'processed 500 records',
    '101 active connections',
  ])('does not treat an unrelated number as an HTTP status: %s', (message) => {
    expect(extractLogFacets(event(message)).status).toBeUndefined()
  })
})

describe('significant HTTP status codes', () => {
  it('accepts exactly the configured dashboard codes', () => {
    const configured = Object.values(SIGNIFICANT_HTTP_STATUS_CODES).flat().map(String)
    expect(configured.every(isSignificantHttpStatus)).toBe(true)
    expect(['102', '203', '300', '405', '501'].some(isSignificantHttpStatus)).toBe(false)
  })
})

describe('facet cache', () => {
  it('reuses facets for an unchanged event and refreshes when its message changes', () => {
    const log = event('{"status_code":503}')
    const first = extractLogFacets(log)
    expect(extractLogFacets(log)).toBe(first)
    log.message = '{"status_code":200}'
    expect(extractLogFacets(log).status).toBe('200')
  })
})
