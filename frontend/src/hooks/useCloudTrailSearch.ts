import { useMutation } from "@tanstack/react-query";

import { searchCloudTrailEvents } from "../api/cloudtrail";
import type { CloudTrailSearchRequest } from "../api/types";
import { useSelectionStore } from "../state/selectionStore";

export function useCloudTrailSearch() {
  const setEvents = useSelectionStore((s) => s.setEvents);
  const appendEvents = useSelectionStore((s) => s.appendEvents);

  return useMutation({
    mutationFn: (request: CloudTrailSearchRequest) => searchCloudTrailEvents(request),
    onSuccess: (data, variables) => {
      if (variables.cursor) {
        appendEvents(data.events);
        return;
      }
      const attrPart = variables.lookup_attribute_key
        ? `, ${variables.lookup_attribute_key}=${variables.lookup_attribute_value}`
        : "";
      const description = `CloudTrail (${variables.start_time} → ${variables.end_time}${attrPart})`;
      setEvents(data.events, description);
    },
  });
}
