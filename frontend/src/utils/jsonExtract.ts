export interface ExtractedJson {
  prefix: string;
  value: unknown;
  suffix: string;
}

const OPEN_TO_CLOSE: Record<string, string> = { "{": "}", "[": "]" };

/**
 * Finds the first balanced {..}/[..] span in a log message that parses as JSON
 * and is an object or array (scalars like a bare number are too ambiguous to
 * treat as "embedded JSON"). Returns the text before/after it so callers can
 * render the surrounding message normally and only pretty-print the JSON part.
 */
export function extractJson(message: string): ExtractedJson | null {
  const trimmed = message.trim();
  try {
    const value: unknown = JSON.parse(trimmed);
    if (value !== null && typeof value === "object") {
      return { prefix: "", value, suffix: "" };
    }
  } catch {
    // not a whole-message JSON payload; look for one embedded in the text
  }

  for (let i = 0; i < message.length; i++) {
    const open = message[i];
    const close = OPEN_TO_CLOSE[open];
    if (!close) continue;

    let depth = 0;
    let inString = false;
    let escape = false;
    for (let j = i; j < message.length; j++) {
      const c = message[j];
      if (inString) {
        if (escape) escape = false;
        else if (c === "\\") escape = true;
        else if (c === '"') inString = false;
        continue;
      }
      if (c === '"') {
        inString = true;
      } else if (c === open) {
        depth++;
      } else if (c === close) {
        depth--;
        if (depth === 0) {
          const candidate = message.slice(i, j + 1);
          try {
            const value: unknown = JSON.parse(candidate);
            if (value !== null && typeof value === "object") {
              return { prefix: message.slice(0, i), value, suffix: message.slice(j + 1) };
            }
          } catch {
            // not valid JSON at this position; keep scanning for the next opener
          }
          break;
        }
      }
    }
  }
  return null;
}
