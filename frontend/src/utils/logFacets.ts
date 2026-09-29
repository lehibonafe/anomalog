import type { LogEvent } from '../api/types'
import { extractJson } from './jsonExtract'

export type LogFacetKey = 'level' | 'method' | 'route' | 'status' | 'exception' | 'duration'
export type LogFacetSelection = Record<LogFacetKey, string[]>
export type ExtractedLogFacets = Partial<Record<LogFacetKey, string>>
export interface FacetHighlightMatch { start: number; end: number; key: LogFacetKey; value: string }

export const EMPTY_LOG_FACETS: LogFacetSelection = {
  level: [], method: [], route: [], status: [], exception: [], duration: [],
}

export const SIGNIFICANT_HTTP_STATUS_CODES = {
  '1xx': [100, 101],
  '2xx': [200, 201, 202, 204],
  '3xx': [301, 302, 304, 307, 308],
  '4xx': [400, 401, 403, 404, 408, 409, 422, 429],
  '5xx': [500, 502, 503, 504],
} as const

const SIGNIFICANT_HTTP_STATUS_SET = new Set<string>(
  Object.values(SIGNIFICANT_HTTP_STATUS_CODES).flat().map(String),
)

export function isSignificantHttpStatus(value: string) {
  return SIGNIFICANT_HTTP_STATUS_SET.has(value)
}

const LEVEL_RE = /\b(TRACE|DEBUG|INFO|WARN(?:ING)?|ERROR|FATAL|CRITICAL)\b/i
const METHOD_RE = /\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\b/i
const REQUEST_RE = /\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+((?:https?:\/\/[^\s]+|\/[^\s?]*))/i
const STATUS_RE = /(?:\bstatus(?:[_ -]?code)?|http\.status_code|response\.status)\s*[=:]\s*["']?([1-5]\d{2})\b/i
const HTTP_RESPONSE_STATUS_RE = /\bHTTP\/\d(?:\.\d)?["']?\s+([1-5]\d{2})\b/i
const HTTP_REQUEST_STATUS_RE = /\b(?:GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+(?:https?:\/\/[^\s"']+|\/[^\s"']*)\s+(?:HTTP\/\d(?:\.\d)?["']?\s+)?([1-5]\d{2})\b/i
const EXCEPTION_RE = /\b([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*(?:Exception|Error))\b/
const DURATION_RE = /\b(?:duration|latency|elapsed|response[_-]?time)(?:_ms)?\s*[=:]\s*["']?(\d+(?:\.\d+)?)\s*(ms|s|sec|seconds?)?\b/i

const FIELD_NAMES: Record<Exclude<LogFacetKey, 'duration'>, string[]> = {
  level: ['level', 'severity', 'log_level', 'loglevel'],
  method: ['method', 'http_method', 'request_method', 'http.method'],
  route: ['route', 'path', 'url', 'request_path', 'http.route', 'http.target'],
  status: ['status', 'status_code', 'statuscode', 'http.status_code', 'response.status'],
  exception: ['exception', 'exception_class', 'error_type', 'error.type'],
}

function flattenObject(value: unknown, prefix = '', output: Record<string, unknown> = {}) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return output
  for (const [key, item] of Object.entries(value as Record<string, unknown>)) {
    const path = prefix ? `${prefix}.${key}` : key
    output[path.toLowerCase()] = item
    if (item && typeof item === 'object' && !Array.isArray(item)) flattenObject(item, path, output)
  }
  return output
}

function field(fields: Record<string, unknown>, names: string[]) {
  for (const name of names) {
    const value = fields[name]
    if (typeof value === 'string' || typeof value === 'number') return String(value)
  }
  return null
}

function normalizeRoute(value: string) {
  let path = value.trim().replace(/["',;}]+$/, '')
  try {
    if (/^https?:\/\//i.test(path)) path = new URL(path).pathname
  } catch {
    // Keep malformed URL-like values usable as plain paths.
  }
  path = path.split('?')[0]
  return path
    .replace(/\/[0-9]+(?=\/|$)/g, '/:id')
    .replace(/\/[0-9a-f]{8}-[0-9a-f-]{27,}(?=\/|$)/gi, '/:id')
    .replace(/\/[0-9a-f]{16,}(?=\/|$)/gi, '/:id')
}

function durationRange(milliseconds: number) {
  if (milliseconds < 100) return '<100 ms'
  if (milliseconds < 500) return '100–500 ms'
  if (milliseconds < 1000) return '500 ms–1 s'
  if (milliseconds < 5000) return '1–5 s'
  return '>5 s'
}

function extractDuration(fields: Record<string, unknown>, message: string) {
  const candidates = ['duration_ms', 'latency_ms', 'elapsed_ms', 'response_time_ms', 'duration', 'latency', 'elapsed', 'response_time']
  for (const name of candidates) {
    const raw = fields[name]
    if (typeof raw !== 'number' && typeof raw !== 'string') continue
    const match = String(raw).match(/^(\d+(?:\.\d+)?)\s*(ms|s|sec|seconds?)?$/i)
    if (!match) continue
    const unit = match[2]?.toLowerCase()
    const milliseconds = Number(match[1]) * (unit?.startsWith('s') ? 1000 : 1)
    return durationRange(milliseconds)
  }
  const match = message.match(DURATION_RE)
  if (!match) return null
  const milliseconds = Number(match[1]) * (match[2]?.toLowerCase().startsWith('s') ? 1000 : 1)
  return durationRange(milliseconds)
}

export function extractLogFacets(event: LogEvent): ExtractedLogFacets {
  const json = extractJson(event.message)
  const fields = flattenObject(json?.value)
  const request = event.message.match(REQUEST_RE)

  const rawLevel = field(fields, FIELD_NAMES.level) ?? event.message.match(LEVEL_RE)?.[1]
  const rawMethod = field(fields, FIELD_NAMES.method) ?? request?.[1] ?? event.message.match(METHOD_RE)?.[1]
  const rawRoute = field(fields, FIELD_NAMES.route) ?? request?.[2]
  const rawStatus = field(fields, FIELD_NAMES.status)
    ?? event.message.match(STATUS_RE)?.[1]
    ?? event.message.match(HTTP_RESPONSE_STATUS_RE)?.[1]
    ?? event.message.match(HTTP_REQUEST_STATUS_RE)?.[1]
  const rawException = field(fields, FIELD_NAMES.exception) ?? event.message.match(EXCEPTION_RE)?.[1]

  const level = rawLevel?.toUpperCase() === 'WARNING' ? 'WARN' : rawLevel?.toUpperCase()
  const status = rawStatus?.match(/^[1-5]\d{2}$/)?.[0]
  const route = rawRoute ? normalizeRoute(rawRoute) : undefined
  const duration = extractDuration(fields, event.message)

  return {
    ...(level ? { level } : {}),
    ...(rawMethod ? { method: rawMethod.toUpperCase() } : {}),
    ...(route ? { route } : {}),
    ...(status ? { status } : {}),
    ...(rawException ? { exception: rawException } : {}),
    ...(duration ? { duration } : {}),
  }
}

export function matchesLogFacets(facets: ExtractedLogFacets, selection: LogFacetSelection) {
  return (Object.keys(selection) as LogFacetKey[]).every((key) => (
    selection[key].length === 0 || (facets[key] !== undefined && selection[key].includes(facets[key]!))
  ))
}

function escaped(value: string) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

export function findSelectedFacetMatches(event: LogEvent, selection: LogFacetSelection): FacetHighlightMatch[] {
  const matches: FacetHighlightMatch[] = []
  const addMatches = (key: LogFacetKey, value: string, regex: RegExp) => {
    for (const match of event.message.matchAll(regex)) {
      if (match.index === undefined || !match[0]) continue
      matches.push({ start: match.index, end: match.index + match[0].length, key, value })
    }
  }

  for (const key of ['level', 'method', 'status', 'exception'] as LogFacetKey[]) {
    for (const value of selection[key]) addMatches(key, value, new RegExp(escaped(value), 'gi'))
  }

  if (selection.route.length) {
    for (const match of event.message.matchAll(/(?:https?:\/\/[^\s"']+|\/[^\s?"']+)/gi)) {
      if (match.index === undefined) continue
      const normalized = normalizeRoute(match[0])
      if (selection.route.includes(normalized)) {
        matches.push({ start: match.index, end: match.index + match[0].length, key: 'route', value: normalized })
      }
    }
  }

  if (selection.duration.length) {
    const durationRegex = new RegExp(DURATION_RE.source, 'gi')
    for (const match of event.message.matchAll(durationRegex)) {
      if (match.index === undefined) continue
      const milliseconds = Number(match[1]) * (match[2]?.toLowerCase().startsWith('s') ? 1000 : 1)
      const value = durationRange(milliseconds)
      if (!selection.duration.includes(value)) continue
      const valueOffset = match[0].indexOf(match[1])
      const text = `${match[1]}${match[2] ? match[0].slice(match[0].indexOf(match[2], valueOffset)) : ''}`
      matches.push({ start: match.index + valueOffset, end: match.index + valueOffset + text.length, key: 'duration', value })
    }
  }

  return matches
}
