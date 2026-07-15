import { useState } from "react";

import { useSelectionStore } from "../../state/selectionStore";
import {
  exceedsMaxTimeRange,
  MAX_TIME_RANGE_DAYS,
  presetToRange,
  TIME_PRESETS,
  type TimePreset,
} from "../../utils/time";

export function TimeRangePicker() {
  const startTime = useSelectionStore((s) => s.startTime);
  const endTime = useSelectionStore((s) => s.endTime);
  const setTimeRange = useSelectionStore((s) => s.setTimeRange);
  const [activePreset, setActivePreset] = useState<TimePreset | null>(null);
  const rangeTooLong = exceedsMaxTimeRange(startTime, endTime);

  const applyPreset = (preset: TimePreset) => {
    const { start, end } = presetToRange(preset, new Date());
    setTimeRange(start, end);
    setActivePreset(preset);
  };

  const clearRange = () => {
    setTimeRange("", "");
    setActivePreset(null);
  };

  return (
    <div className="panel-section">
      <div className="panel-section-title title-with-action">
        Time range
        {(startTime || endTime) && (
          <button type="button" className="link-button" onClick={clearRange}>
            Clear
          </button>
        )}
      </div>
      <div className="preset-row">
        {TIME_PRESETS.map((p) => (
          <button
            key={p.value}
            type="button"
            className={activePreset === p.value ? "chip active" : "chip"}
            onClick={() => applyPreset(p.value)}
          >
            {p.label}
          </button>
        ))}
      </div>
      <div className="custom-range-row">
        <label>
          Start
          <input
            type="datetime-local"
            value={toLocalInput(startTime)}
            onChange={(e) => {
              setTimeRange(fromLocalInput(e.target.value), endTime);
              setActivePreset(null);
            }}
          />
        </label>
        <label>
          End
          <input
            type="datetime-local"
            value={toLocalInput(endTime)}
            onChange={(e) => {
              setTimeRange(startTime, fromLocalInput(e.target.value));
              setActivePreset(null);
            }}
          />
        </label>
      </div>
      {rangeTooLong && (
        <p className="error-text">
          Range exceeds {MAX_TIME_RANGE_DAYS} days — narrow it to avoid scanning large log
          volumes and unexpected AWS charges.
        </p>
      )}
    </div>
  );
}

function toLocalInput(iso: string): string {
  if (!iso) return "";
  const d = new Date(iso);
  const offset = d.getTimezoneOffset();
  const local = new Date(d.getTime() - offset * 60000);
  return local.toISOString().slice(0, 16);
}

function fromLocalInput(value: string): string {
  if (!value) return "";
  return new Date(value).toISOString();
}
