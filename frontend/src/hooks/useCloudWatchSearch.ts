import { useMutation } from "@tanstack/react-query";

import { searchCloudWatchLogs } from "../api/cloudwatch";
import type { CloudWatchSearchRequest } from "../api/types";
import { useSelectionStore } from "../state/selectionStore";

export function useCloudWatchSearch() {
  const setEvents = useSelectionStore((s) => s.setEvents);

  return useMutation({
    mutationFn: (request: CloudWatchSearchRequest) => searchCloudWatchLogs(request),
    onSuccess: (data, variables) => {
      const filterPart = variables.filter_pattern
        ? `, filter="${variables.filter_pattern}"`
        : "";
      const description = `CloudWatch ${variables.log_group_names.join(", ")} (${variables.start_time} → ${variables.end_time}${filterPart})`;
      setEvents(data.events, description);
    },
  });
}
