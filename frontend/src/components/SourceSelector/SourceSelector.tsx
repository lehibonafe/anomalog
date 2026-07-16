import { useSelectionStore } from "../../state/selectionStore";
import { CloudTrailSourcePicker } from "./CloudTrailSourcePicker";
import { CloudWatchSourcePicker } from "./CloudWatchSourcePicker";

export function SourceSelector() {
  const sourceMode = useSelectionStore((s) => s.sourceMode);
  const setSourceMode = useSelectionStore((s) => s.setSourceMode);

  return (
    <div className="panel-section">
      <div className="tab-row">
        <button
          type="button"
          className={sourceMode === "cloudwatch" ? "tab active" : "tab"}
          onClick={() => setSourceMode("cloudwatch")}
        >
          CloudWatch
        </button>
        <button
          type="button"
          className={sourceMode === "cloudtrail" ? "tab active" : "tab"}
          onClick={() => setSourceMode("cloudtrail")}
        >
          CloudTrail
        </button>
      </div>
      {sourceMode === "cloudwatch" && <CloudWatchSourcePicker />}
      {sourceMode === "cloudtrail" && <CloudTrailSourcePicker />}
    </div>
  );
}
