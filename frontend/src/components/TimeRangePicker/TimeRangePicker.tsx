import { useState } from "react";

import { useSelectionStore } from "../../state/selectionStore";
import {
  DISPLAY_TIME_ZONE_LABEL,
  exceedsMaxTimeRange,
  fromSingaporeInput,
  MAX_TIME_RANGE_DAYS,
  presetToRange,
  TIME_PRESETS,
  toSingaporeInput,
  type TimePreset,
} from "../../utils/time";

export function TimeRangePicker() {
  const startTime = useSelectionStore((s) => s.startTime);
  const endTime = useSelectionStore((s) => s.endTime);
  const setTimeRange = useSelectionStore((s) => s.setTimeRange);
  const [activePreset, setActivePreset] = useState<TimePreset | null>(null);
  const rangeTooLong = exceedsMaxTimeRange(startTime, endTime);

  const nowLocal = toSingaporeInput(new Date().toISOString());
  const startLocal = toSingaporeInput(startTime);
  const endLocal = toSingaporeInput(endTime);
  // datetime-local values are zero-padded "YYYY-MM-DDTHH:mm", so string
  // comparison sorts the same as chronological order.
  const startMax = endLocal && endLocal < nowLocal ? endLocal : nowLocal;
  const endMin = startLocal || undefined;
  const endMax = nowLocal;

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
        Time range ({DISPLAY_TIME_ZONE_LABEL})
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
            value={startLocal}
            max={startMax}
            onChange={(e) => {
              const value = e.target.value > startMax ? startMax : e.target.value;
              setTimeRange(fromSingaporeInput(value), endTime);
              setActivePreset(null);
            }}
          />
        </label>
        <label>
          End
          <input
            type="datetime-local"
            value={endLocal}
            min={endMin}
            max={endMax}
            onChange={(e) => {
              let value = e.target.value;
              if (endMin && value < endMin) value = endMin;
              if (value > endMax) value = endMax;
              setTimeRange(startTime, fromSingaporeInput(value));
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
