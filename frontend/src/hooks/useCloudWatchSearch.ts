import { useMutation } from "@tanstack/react-query";

import { searchCloudWatchLogs } from "../api/cloudwatch";
import type { CloudWatchSearchRequest } from "../api/types";
import { useSelectionStore } from "../state/selectionStore";

export function useCloudWatchSearch() {
  const setEvents = useSelectionStore((s) => s.setEvents);
  const appendEvents = useSelectionStore((s) => s.appendEvents);
  const setCloudWatchNextRequest = useSelectionStore((s) => s.setCloudWatchNextRequest);

  return useMutation({
    mutationFn: (request: CloudWatchSearchRequest) => searchCloudWatchLogs(request),
    onMutate: (variables) => {
      if (!variables.cursor) setCloudWatchNextRequest(null);
    },
    onSuccess: (data, variables) => {
      if (variables.cursor) {
        appendEvents(data.events);
      } else {
        const filterPart = variables.filter_pattern
          ? `, filter="${variables.filter_pattern}"`
          : "";
        const description = `CloudWatch ${variables.log_group_names.join(", ")} (${variables.start_time} → ${variables.end_time}${filterPart})`;
        setEvents(data.events, description);
      }

      setCloudWatchNextRequest(data.cursor ? { ...variables, cursor: data.cursor } : null);
    },
  });
}
