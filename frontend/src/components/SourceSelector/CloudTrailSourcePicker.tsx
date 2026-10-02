import type { CloudTrailAccountId, CloudTrailLookupAttributeKey } from "../../api/types";
import { useSelectionStore } from "../../state/selectionStore";

const CLOUDTRAIL_ACCOUNTS: Array<{ id: CloudTrailAccountId; name: string }> = [
  { id: "887350548529", name: "ETAP DEVOPS" },
  { id: "065031412132", name: "ETAP ECPAY" },
  { id: "221315724874", name: "ETAP INC" },
  { id: "550222016520", name: "ETAP MONITORING" },
  { id: "679437835821", name: "ETAP SRE" },
  { id: "765186506449", name: "ETAP SYSOPS" },
];

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
  const accountId = useSelectionStore((s) => s.cloudTrailAccountId);
  const setAccountId = useSelectionStore((s) => s.setCloudTrailAccountId);
  const attributeKey = useSelectionStore((s) => s.cloudTrailAttributeKey);
  const setAttributeKey = useSelectionStore((s) => s.setCloudTrailAttributeKey);
  const attributeValue = useSelectionStore((s) => s.cloudTrailAttributeValue);
  const setAttributeValue = useSelectionStore((s) => s.setCloudTrailAttributeValue);

  return (
    <div className="panel-section">
      <div className="panel-section-title">CloudTrail events</div>
      <p className="hint">
        Search automatically discovered organization events by account and optional
        attribute.
      </p>
      <div className="custom-range-row">
        <label>
          Account
          <select
            value={accountId}
            onChange={(e) => setAccountId(e.target.value as CloudTrailAccountId | "")}
          >
            <option value="">All accounts</option>
            {CLOUDTRAIL_ACCOUNTS.map((account) => (
              <option key={account.id} value={account.id}>
                {account.name} — {account.id}
              </option>
            ))}
          </select>
        </label>
        <label>
          Attribute
          <select
            value={attributeKey}
            onChange={(e) => setAttributeKey(e.target.value as CloudTrailLookupAttributeKey | "")}
          >
            <option value="">All</option>
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
