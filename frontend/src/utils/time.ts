export type TimePreset = "15m" | "1h" | "24h" | "7d";

export const MAX_TIME_RANGE_DAYS = 7;
export const DISPLAY_TIME_ZONE = "Asia/Singapore";
export const DISPLAY_TIME_ZONE_LABEL = "SGT";

const singaporeInputFormatter = new Intl.DateTimeFormat("en-CA", {
  timeZone: DISPLAY_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

const singaporeChartDateTimeFormatter = new Intl.DateTimeFormat("en-US", {
  timeZone: DISPLAY_TIME_ZONE,
  month: "short",
  day: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

const singaporeChartTimeFormatter = new Intl.DateTimeFormat("en-GB", {
  timeZone: DISPLAY_TIME_ZONE,
  hour: "2-digit",
  minute: "2-digit",
  hourCycle: "h23",
});

export function exceedsMaxTimeRange(start: string, end: string): boolean {
  if (!start || !end) return false;
  const ms = new Date(end).getTime() - new Date(start).getTime();
  return ms > MAX_TIME_RANGE_DAYS * 24 * 60 * 60 * 1000;
}

export const TIME_PRESETS: { value: TimePreset; label: string }[] = [
  { value: "15m", label: "Last 15 minutes" },
  { value: "1h", label: "Last 1 hour" },
  { value: "24h", label: "Last 24 hours" },
  { value: "7d", label: "Last 7 days" },
];

const PRESET_DURATION_MS: Record<TimePreset, number> = {
  '15m': 15 * 60_000,
  '1h': 60 * 60_000,
  '24h': 24 * 60 * 60_000,
  '7d': 7 * 24 * 60 * 60_000,
};

export function presetToRange(preset: TimePreset, now: Date): { start: string; end: string } {
  const start = new Date(now.getTime() - PRESET_DURATION_MS[preset]);
  return { start: start.toISOString(), end: now.toISOString() };
}

export function formatTimestamp(ts: string | null): string {
  if (!ts) return "";
  const value = new Date(ts);
  if (Number.isNaN(value.getTime())) return "";
  return `${value.toLocaleString(undefined, { timeZone: DISPLAY_TIME_ZONE })} ${DISPLAY_TIME_ZONE_LABEL}`;
}

export function formatSingaporeDateTime(value: Date): string {
  return singaporeChartDateTimeFormatter.format(value);
}

export function formatSingaporeTime(value: Date): string {
  return singaporeChartTimeFormatter.format(value);
}

export function toSingaporeInput(iso: string): string {
  if (!iso) return "";
  const value = new Date(iso);
  if (Number.isNaN(value.getTime())) return "";
  const parts = Object.fromEntries(
    singaporeInputFormatter
      .formatToParts(value)
      .filter((part) => part.type !== "literal")
      .map((part) => [part.type, part.value]),
  );
  return `${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;
}

export function fromSingaporeInput(value: string): string {
  if (!value) return "";
  const instant = new Date(`${value}:00+08:00`);
  return Number.isNaN(instant.getTime()) ? "" : instant.toISOString();
}
