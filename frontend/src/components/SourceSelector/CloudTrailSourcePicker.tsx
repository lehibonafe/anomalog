import type { CloudTrailLookupAttributeKey } from "../../api/types";
import { useSelectionStore } from "../../state/selectionStore";

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
  const attributeKey = useSelectionStore((s) => s.cloudTrailAttributeKey);
  const setAttributeKey = useSelectionStore((s) => s.setCloudTrailAttributeKey);
  const attributeValue = useSelectionStore((s) => s.cloudTrailAttributeValue);
  const setAttributeValue = useSelectionStore((s) => s.setCloudTrailAttributeValue);

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
    </div>
  );
}
