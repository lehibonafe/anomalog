import { isAxiosError } from "axios";

import { useCloudWatchSearch } from "../../hooks/useCloudWatchSearch";
import { useSelectionStore } from "../../state/selectionStore";
import { exceedsMaxTimeRange } from "../../utils/time";

export function FilterBar() {
  const sourceMode = useSelectionStore((s) => s.sourceMode);
  const filterPattern = useSelectionStore((s) => s.filterPattern);
  const setFilterPattern = useSelectionStore((s) => s.setFilterPattern);
  const logGroupNames = useSelectionStore((s) => s.logGroupNames);
  const startTime = useSelectionStore((s) => s.startTime);
  const endTime = useSelectionStore((s) => s.endTime);

  const search = useCloudWatchSearch();

  if (sourceMode !== "cloudwatch") {
    return null;
  }

  const rangeTooLong = exceedsMaxTimeRange(startTime, endTime);
  const canSearch = logGroupNames.length > 0 && !!startTime && !!endTime && !rangeTooLong;

  return (
    <div className="panel-section">
      <div className="panel-section-title">Filter pattern (CloudWatch Logs syntax)</div>
      <input
        type="text"
        placeholder='e.g. ERROR or "timeout"'
        value={filterPattern}
        onChange={(e) => setFilterPattern(e.target.value)}
      />
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
