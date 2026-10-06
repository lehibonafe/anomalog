import { isAxiosError } from "axios";

import type { CloudTrailSearchRequest } from "../../api/types";
import { useCloudTrailSearch } from "../../hooks/useCloudTrailSearch";
import { useAppConfig } from "../../hooks/useAppConfig";
import { useSelectionStore } from "../../state/selectionStore";
import { exceedsMaxTimeRange } from "../../utils/time";

export function CloudTrailSearchBar() {
  const sourceMode = useSelectionStore((s) => s.sourceMode);
  const startTime = useSelectionStore((s) => s.startTime);
  const endTime = useSelectionStore((s) => s.endTime);
  const accountId = useSelectionStore((s) => s.cloudTrailAccountId);
  const attributeKey = useSelectionStore((s) => s.cloudTrailAttributeKey);
  const attributeValue = useSelectionStore((s) => s.cloudTrailAttributeValue);

  const search = useCloudTrailSearch();
  const { data: config } = useAppConfig();

  if (sourceMode !== "cloudtrail") {
    return null;
  }

  const rangeTooLong = exceedsMaxTimeRange(startTime, endTime);
  const hasIncompleteAttribute = !!attributeKey !== !!attributeValue.trim();
  const canSearch = !!startTime && !!endTime && !rangeTooLong && !hasIncompleteAttribute
    && (!accountId || config?.cloudtrail_account_filter_available === true);

  const runSearch = () => {
    const request: CloudTrailSearchRequest = {
      start_time: startTime,
      end_time: endTime,
      account_id: accountId || null,
      lookup_attribute_key: attributeKey || null,
      lookup_attribute_value: attributeValue.trim() || null,
    };
    search.reset(); // drop any stale truncated/cursor state from a previous query
    search.mutate(request);
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
    </div>
  );
}
