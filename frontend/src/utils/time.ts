import { differenceInMilliseconds, subDays, subHours, subMinutes } from "date-fns";

export type TimePreset = "15m" | "1h" | "24h" | "7d";

export const MAX_TIME_RANGE_DAYS = 7;

export function exceedsMaxTimeRange(start: string, end: string): boolean {
  if (!start || !end) return false;
  const ms = differenceInMilliseconds(new Date(end), new Date(start));
  return ms > MAX_TIME_RANGE_DAYS * 24 * 60 * 60 * 1000;
}

export const TIME_PRESETS: { value: TimePreset; label: string }[] = [
  { value: "15m", label: "Last 15 minutes" },
  { value: "1h", label: "Last 1 hour" },
  { value: "24h", label: "Last 24 hours" },
  { value: "7d", label: "Last 7 days" },
];

export function presetToRange(preset: TimePreset, now: Date): { start: string; end: string } {
  let start: Date;
  switch (preset) {
    case "15m":
      start = subMinutes(now, 15);
      break;
    case "1h":
      start = subHours(now, 1);
      break;
    case "24h":
      start = subHours(now, 24);
      break;
    case "7d":
      start = subDays(now, 7);
      break;
  }
  return { start: start.toISOString(), end: now.toISOString() };
}

export function formatTimestamp(ts: string | null): string {
  if (!ts) return "";
  return new Date(ts).toLocaleString();
}
