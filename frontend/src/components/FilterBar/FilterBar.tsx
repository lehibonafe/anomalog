import { useSelectionStore } from "../../state/selectionStore";

export function FilterBar() {
  const sourceMode = useSelectionStore((s) => s.sourceMode);
  const filterPattern = useSelectionStore((s) => s.filterPattern);
  const setFilterPattern = useSelectionStore((s) => s.setFilterPattern);

  if (sourceMode !== "cloudwatch") {
    return null;
  }

  return (
    <div className="panel-section">
      <div className="panel-section-title">Filter pattern (CloudWatch Logs syntax)</div>
      <input
        type="text"
        placeholder='e.g. ERROR or "timeout"'
        value={filterPattern}
        onChange={(e) => setFilterPattern(e.target.value)}
      />
    </div>
  );
}
