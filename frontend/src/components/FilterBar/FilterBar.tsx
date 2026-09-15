import { isAxiosError } from "axios";
import { useState } from "react";

import type { CloudWatchSearchRequest } from "../../api/types";
import { useCloudWatchSearch } from "../../hooks/useCloudWatchSearch";
import { useSelectionStore } from "../../state/selectionStore";
import { exceedsMaxTimeRange } from "../../utils/time";
import { LiveTailControls } from "./LiveTailControls";

export function FilterBar() {
  const sourceMode = useSelectionStore((s) => s.sourceMode);
  const filterPattern = useSelectionStore((s) => s.filterPattern);
  const setFilterPattern = useSelectionStore((s) => s.setFilterPattern);
  const logGroupNames = useSelectionStore((s) => s.logGroupNames);
  const startTime = useSelectionStore((s) => s.startTime);
  const endTime = useSelectionStore((s) => s.endTime);
  const loadedCount = useSelectionStore((s) => s.events.length);

  const search = useCloudWatchSearch();
  // Snapshot of the request that produced the current cursor, so "Load more"
  // keeps paging the same query even if the sidebar inputs change afterward.
  const [lastRequest, setLastRequest] = useState<CloudWatchSearchRequest | null>(null);
  const [liveTailRunning, setLiveTailRunning] = useState(false);

  if (sourceMode !== "cloudwatch") {
    return null;
  }

  const rangeTooLong = exceedsMaxTimeRange(startTime, endTime);
  const canSearch = logGroupNames.length > 0 && !!startTime && !!endTime && !rangeTooLong;

  const runSearch = () => {
    const request: CloudWatchSearchRequest = {
      log_group_names: logGroupNames,
      start_time: startTime,
      end_time: endTime,
      filter_pattern: filterPattern || null,
    };
    setLastRequest(request);
    search.reset(); // drop any stale truncated/cursor state from a previous query
    search.mutate(request);
  };

  const loadMore = () => {
    if (!lastRequest || !search.data?.cursor) return;
    search.mutate({ ...lastRequest, cursor: search.data.cursor });
  };

  return (
    <div className="panel-section">
      <div className="panel-section-title">Filter pattern (CloudWatch Logs syntax)</div>
      <input
        type="text"
        placeholder='e.g. ERROR or "timeout"'
        value={filterPattern}
        disabled={liveTailRunning}
        onChange={(e) => setFilterPattern(e.target.value)}
      />
      <button
        type="button"
        className="btn-primary btn-block"
        disabled={!canSearch || search.isPending || liveTailRunning}
        onClick={runSearch}
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
      {search.data?.cursor && (
        <div className="load-more-row">
          <p className="hint">
            Showing {loadedCount.toLocaleString()} lines · Continue loading to check for more results.
          </p>
          <button
            type="button"
            className="btn-block"
            disabled={search.isPending || liveTailRunning}
            onClick={loadMore}
          >
            {search.isPending && <span className="spinner dark" />}
            {search.isPending ? "Loading..." : "Load more"}
          </button>
        </div>
      )}
      <LiveTailControls onRunningChange={setLiveTailRunning} />
    </div>
  );
}
