import { isAxiosError } from "axios";
import { useState } from "react";

import type { CloudTrailLookupAttributeKey } from "../../api/types";
import { useCloudTrailSearch } from "../../hooks/useCloudTrailSearch";
import { useSelectionStore } from "../../state/selectionStore";
import { exceedsMaxTimeRange } from "../../utils/time";

const LOOKUP_ATTRIBUTE_KEYS: CloudTrailLookupAttributeKey[] = [
  "EventName",
  "Username",
  "EventSource",
  "ResourceName",
  "ResourceType",
  "AccessKeyId",
  "EventId",
  "ReadOnly",
];

export function CloudTrailSourcePicker() {
  const [attributeKey, setAttributeKey] = useState<CloudTrailLookupAttributeKey | "">("");
  const [attributeValue, setAttributeValue] = useState("");

  const startTime = useSelectionStore((s) => s.startTime);
  const endTime = useSelectionStore((s) => s.endTime);

  const search = useCloudTrailSearch();

  const rangeTooLong = exceedsMaxTimeRange(startTime, endTime);
  const hasIncompleteAttribute = !!attributeKey !== !!attributeValue.trim();
  const canSearch = !!startTime && !!endTime && !rangeTooLong && !hasIncompleteAttribute;

  return (
    <div className="panel-section">
      <div className="panel-section-title">CloudTrail event history</div>
      <p className="hint">
        Filter by an attribute (optional) — leave blank to fetch every event in the time
        range.
      </p>
      <div className="custom-range-row">
        <label>
          Attribute
          <select
            value={attributeKey}
            onChange={(e) => setAttributeKey(e.target.value as CloudTrailLookupAttributeKey | "")}
          >
            <option value="">None</option>
            {LOOKUP_ATTRIBUTE_KEYS.map((key) => (
              <option key={key} value={key}>
                {key}
              </option>
            ))}
          </select>
        </label>
        <label>
          Value
          <input
            type="text"
            placeholder="e.g. ConsoleLogin"
            value={attributeValue}
            onChange={(e) => setAttributeValue(e.target.value)}
            disabled={!attributeKey}
          />
        </label>
      </div>
      <button
        type="button"
        className="btn-primary btn-block"
        disabled={!canSearch || search.isPending}
        onClick={() =>
          search.mutate({
            start_time: startTime,
            end_time: endTime,
            lookup_attribute_key: attributeKey || null,
            lookup_attribute_value: attributeValue.trim() || null,
          })
        }
      >
        {search.isPending && <span className="spinner" />}
        {search.isPending ? "Searching..." : "Search events"}
      </button>
      {search.isError && (
        <p className="error-text">
          {isAxiosError(search.error) && search.error.response?.status === 400
            ? search.error.response?.data?.detail
            : "Search failed. Check the backend logs."}
        </p>
      )}
    </div>
  );
}
