import { useState } from "react";

import { useBuckets, useS3Content, useS3Objects } from "../../hooks/useS3Objects";
import { useSelectionStore } from "../../state/selectionStore";

export function S3SourcePicker() {
  const [prefix, setPrefix] = useState("");
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);

  const bucket = useSelectionStore((s) => s.bucket);
  const setBucket = useSelectionStore((s) => s.setBucket);
  const startTime = useSelectionStore((s) => s.startTime);
  const endTime = useSelectionStore((s) => s.endTime);

  const buckets = useBuckets();
  const objects = useS3Objects({ bucket, prefix, start: startTime, end: endTime });
  const content = useS3Content();

  const toggleKey = (key: string) => {
    setSelectedKeys((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  };

  const visibleKeys = objects.data?.objects.map((o) => o.key) ?? [];
  const allVisibleSelected =
    visibleKeys.length > 0 && visibleKeys.every((k) => selectedKeys.includes(k));

  const toggleSelectAll = () => {
    setSelectedKeys(allVisibleSelected ? [] : visibleKeys);
  };

  return (
    <div className="panel-section">
      <div className="panel-section-title">S3 bucket + prefix</div>
      <select
        value={bucket ?? ""}
        onChange={(e) => {
          setBucket(e.target.value || null);
          setSelectedKeys([]);
        }}
      >
        <option value="">Select a bucket...</option>
        {buckets.data?.buckets.map((b) => (
          <option key={b.name} value={b.name}>
            {b.name}
          </option>
        ))}
      </select>
      <input
        type="text"
        placeholder="Key prefix (e.g. app/2026-07-09/)"
        value={prefix}
        onChange={(e) => setPrefix(e.target.value)}
      />
      {objects.isLoading && <p className="hint">Loading objects...</p>}
      {objects.error && <p className="error-text">Failed to list objects.</p>}
      {visibleKeys.length > 0 && (
        <div className="title-with-action">
          <span className="hint">
            {selectedKeys.length} of {visibleKeys.length} selected
          </span>
          <button type="button" className="link-button" onClick={toggleSelectAll}>
            {allVisibleSelected ? "Deselect all" : "Select all"}
          </button>
        </div>
      )}
      <ul className="checkbox-list">
        {objects.data?.objects.map((obj) => (
          <li key={obj.key}>
            <label>
              <input
                type="checkbox"
                checked={selectedKeys.includes(obj.key)}
                onChange={() => toggleKey(obj.key)}
              />
              {obj.key} ({obj.size} bytes)
            </label>
          </li>
        ))}
        {objects.data && objects.data.objects.length === 0 && (
          <li className="hint">No objects found in this time range/prefix.</li>
        )}
      </ul>
      <button
        type="button"
        className="btn-primary btn-block"
        disabled={!bucket || selectedKeys.length === 0 || content.isPending}
        onClick={() => bucket && content.mutate({ bucket, keys: selectedKeys })}
      >
        {content.isPending && <span className="spinner" />}
        {content.isPending ? "Loading..." : "Load selected objects"}
      </button>
      {content.isError && <p className="error-text">Failed to load object content.</p>}
    </div>
  );
}
