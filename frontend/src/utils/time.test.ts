import { describe, expect, it } from 'vitest'

import { exceedsMaxTimeRange, presetToRange } from './time'

describe('time presets', () => {
  it.each([
    ['15m', 15 * 60_000],
    ['1h', 60 * 60_000],
    ['24h', 24 * 60 * 60_000],
    ['7d', 7 * 24 * 60 * 60_000],
  ] as const)('subtracts the expected duration for %s', (preset, duration) => {
    const now = new Date('2026-10-06T12:34:56.000Z')
    const range = presetToRange(preset, now)
    expect(range.end).toBe(now.toISOString())
    expect(new Date(range.end).getTime() - new Date(range.start).getTime()).toBe(duration)
  })

  it('accepts seven days and rejects longer ranges', () => {
    const start = '2026-10-01T00:00:00.000Z'
    expect(exceedsMaxTimeRange(start, '2026-10-08T00:00:00.000Z')).toBe(false)
    expect(exceedsMaxTimeRange(start, '2026-10-08T00:00:00.001Z')).toBe(true)
  })
})
