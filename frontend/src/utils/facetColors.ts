import type { LogFacetKey } from './logFacets'

const PALETTE = ['#5b8def', '#3fb572', '#e0a13a', '#f0575d', '#9b7de5', '#38b7b0', '#d56da1', '#8b9bad']
const OFFSETS: Record<LogFacetKey, number> = {
  level: 3,
  method: 0,
  route: 4,
  status: 1,
  exception: 6,
  duration: 2,
}

const HTTP_STATUS_COLORS: Record<string, string> = {
  '1': 'var(--status-1xx)',
  '2': 'var(--status-2xx)',
  '3': 'var(--status-3xx)',
  '4': 'var(--status-4xx)',
  '5': 'var(--status-5xx)',
}

export function facetColor(key: LogFacetKey, value: string) {
  if (key === 'status' && /^[1-5]\d{2}$/.test(value)) {
    return HTTP_STATUS_COLORS[value[0]]
  }
  let hash = 0
  for (let index = 0; index < value.length; index += 1) hash = (hash * 31 + value.charCodeAt(index)) >>> 0
  return PALETTE[(hash + OFFSETS[key]) % PALETTE.length]
}
