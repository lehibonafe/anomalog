import { isAxiosError } from "axios";
import { useState } from "react";

import type { CloudTrailSearchRequest } from "../../api/types";
import { useCloudTrailSearch } from "../../hooks/useCloudTrailSearch";
import { useSelectionStore } from "../../state/selectionStore";
import { exceedsMaxTimeRange } from "../../utils/time";

export function CloudTrailSearchBar() {
  const sourceMode = useSelectionStore((s) => s.sourceMode);
  const startTime = useSelectionStore((s) => s.startTime);
  const endTime = useSelectionStore((s) => s.endTime);
  const attributeKey = useSelectionStore((s) => s.cloudTrailAttributeKey);
  const attributeValue = useSelectionStore((s) => s.cloudTrailAttributeValue);
  const loadedCount = useSelectionStore((s) => s.events.length);

  const search = useCloudTrailSearch();
  // Snapshot of the request that produced the current cursor, so "Load more"
  // keeps paging the same query even if the sidebar inputs change afterward.
  const [lastRequest, setLastRequest] = useState<CloudTrailSearchRequest | null>(null);

  if (sourceMode !== "cloudtrail") {
    return null;
  }

  const rangeTooLong = exceedsMaxTimeRange(startTime, endTime);
  const hasIncompleteAttribute = !!attributeKey !== !!attributeValue.trim();
  const canSearch = !!startTime && !!endTime && !rangeTooLong && !hasIncompleteAttribute;

  const runSearch = () => {
    const request: CloudTrailSearchRequest = {
      start_time: startTime,
      end_time: endTime,
      lookup_attribute_key: attributeKey || null,
      lookup_attribute_value: attributeValue.trim() || null,
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
      <button
        type="button"
        className="btn-primary btn-block"
        disabled={!canSearch || search.isPending}
        onClick={runSearch}
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
      {search.data?.truncated && (
        <div className="load-more-row">
          <p className="hint">
            Showing {loadedCount.toLocaleString()} events — more match this query.
          </p>
          <button
            type="button"
            className="btn-block"
            disabled={search.isPending}
            onClick={loadMore}
          >
            {search.isPending && <span className="spinner dark" />}
            {search.isPending ? "Loading..." : "Load more"}
          </button>
        </div>
      )}
    </div>
  );
}
