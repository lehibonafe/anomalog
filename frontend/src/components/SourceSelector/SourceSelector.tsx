import { useSelectionStore } from "../../state/selectionStore";
import { CloudTrailSourcePicker } from "./CloudTrailSourcePicker";
import { CloudWatchSourcePicker } from "./CloudWatchSourcePicker";
import { S3SourcePicker } from "./S3SourcePicker";

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
          className={sourceMode === "s3" ? "tab active" : "tab"}
          onClick={() => setSourceMode("s3")}
        >
          S3
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
      {sourceMode === "s3" && <S3SourcePicker />}
      {sourceMode === "cloudtrail" && <CloudTrailSourcePicker />}
    </div>
  );
}
