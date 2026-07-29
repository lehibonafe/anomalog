import { useState } from "react";

import { useLogGroups } from "../../hooks/useLogGroups";
import { useSelectionStore } from "../../state/selectionStore";

export function CloudWatchSourcePicker() {
  const [prefix, setPrefix] = useState("");
  const { data, isLoading, error } = useLogGroups(prefix);

  const logGroupNames = useSelectionStore((s) => s.logGroupNames);
  const setLogGroupNames = useSelectionStore((s) => s.setLogGroupNames);

  const toggleGroup = (name: string) => {
    setLogGroupNames(
      logGroupNames.includes(name)
        ? logGroupNames.filter((n) => n !== name)
        : [...logGroupNames, name]
    );
  };

  return (
    <div className="panel-section">
      <div className="panel-section-title">CloudWatch log groups</div>
      <input
        type="text"
        placeholder="Filter by prefix..."
        value={prefix}
        onChange={(e) => setPrefix(e.target.value)}
      />
      {isLoading && <p className="hint">Loading log groups...</p>}
      {error && <p className="error-text">Failed to load log groups.</p>}
      <ul className="checkbox-list">
        {data?.log_groups.map((group) => (
          <li key={group.name}>
            <label>
              <input
                type="checkbox"
                checked={logGroupNames.includes(group.name)}
                onChange={() => toggleGroup(group.name)}
              />
              {group.name}
            </label>
          </li>
        ))}
        {data && data.log_groups.length === 0 && (
          <li className="hint">No log groups found.</li>
        )}
      </ul>
    </div>
  );
}
