import { isAxiosError } from "axios";
import { useState } from "react";

import { useCloudWatchSearch } from "../../hooks/useCloudWatchSearch";
import { useLogGroups } from "../../hooks/useLogGroups";
import { useSelectionStore } from "../../state/selectionStore";
import { exceedsMaxTimeRange } from "../../utils/time";

export function CloudWatchSourcePicker() {
  const [prefix, setPrefix] = useState("");
  const { data, isLoading, error } = useLogGroups(prefix);

  const logGroupNames = useSelectionStore((s) => s.logGroupNames);
  const setLogGroupNames = useSelectionStore((s) => s.setLogGroupNames);
  const startTime = useSelectionStore((s) => s.startTime);
  const endTime = useSelectionStore((s) => s.endTime);
  const filterPattern = useSelectionStore((s) => s.filterPattern);

  const search = useCloudWatchSearch();

  const toggleGroup = (name: string) => {
    setLogGroupNames(
      logGroupNames.includes(name)
        ? logGroupNames.filter((n) => n !== name)
        : [...logGroupNames, name]
    );
  };

  const rangeTooLong = exceedsMaxTimeRange(startTime, endTime);
  const canSearch = logGroupNames.length > 0 && !!startTime && !!endTime && !rangeTooLong;

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
      <button
        type="button"
        className="btn-primary btn-block"
        disabled={!canSearch || search.isPending}
        onClick={() =>
          search.mutate({
            log_group_names: logGroupNames,
            start_time: startTime,
            end_time: endTime,
            filter_pattern: filterPattern || null,
          })
        }
      >
        {search.isPending && <span className="spinner" />}
        {search.isPending ? "Searching..." : "Search logs"}
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
