import { useState } from "react";

import { useDebouncedValue } from "../../hooks/useDebouncedValue";
import { useLogGroups } from "../../hooks/useLogGroups";
import { useSelectionStore } from "../../state/selectionStore";

export function CloudWatchSourcePicker() {
  const [prefix, setPrefix] = useState("");
  const debouncedPrefix = useDebouncedValue(prefix, 300);
  const {
    data,
    isLoading,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useLogGroups(debouncedPrefix);
  const logGroups = data?.pages.flatMap((page) => page.log_groups) ?? [];

  const logGroupNames = useSelectionStore((s) => s.logGroupNames);
  const setLogGroupNames = useSelectionStore((s) => s.setLogGroupNames);

  const toggleGroup = (identifier: string) => {
    if (logGroupNames.includes(identifier)) {
      setLogGroupNames(logGroupNames.filter((name) => name !== identifier));
    } else {
      setLogGroupNames([...logGroupNames, identifier]);
    }
  };

  return (
    <div className="panel-section">
      <div className="panel-section-title title-with-action">
        CloudWatch log groups
        {logGroupNames.length > 0 && (
          <button type="button" className="link-button" onClick={() => setLogGroupNames([])}>
            {logGroupNames.length} selected · Clear
          </button>
        )}
      </div>
      <input
        type="text"
        placeholder="Filter by prefix..."
        value={prefix}
        onChange={(e) => setPrefix(e.target.value)}
      />
      {isLoading && <p className="hint">Loading log groups...</p>}
      {error && <p className="error-text">Failed to load log groups.</p>}
      <ul className="checkbox-list">
        {logGroups.map((group) => {
          const identifier = group.identifier || group.name;
          return (
            <li key={identifier}>
              <label>
                <input
                  type="checkbox"
                  checked={logGroupNames.includes(identifier)}
                  onChange={() => toggleGroup(identifier)}
                />
                {group.name}
                {group.account_id && ` (owner: ${group.account_id})`}
              </label>
            </li>
          );
        })}
        {data && logGroups.length === 0 && (
          <li className="hint">No log groups found.</li>
        )}
      </ul>
      {hasNextPage && (
        <button
          type="button"
          className="secondary-button"
          disabled={isFetchingNextPage}
          onClick={() => fetchNextPage()}
        >
          {isFetchingNextPage ? "Loading more…" : "Load more log groups"}
        </button>
      )}
    </div>
  );
}
