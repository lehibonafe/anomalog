import { useMutation } from "@tanstack/react-query";

import { searchCloudTrailEvents } from "../api/cloudtrail";
import type { CloudTrailSearchRequest } from "../api/types";
import { useSelectionStore } from "../state/selectionStore";

export function useCloudTrailSearch() {
  const setEvents = useSelectionStore((s) => s.setEvents);

  return useMutation({
    mutationFn: (request: CloudTrailSearchRequest) => searchCloudTrailEvents(request),
    onSuccess: (data, variables) => {
      const attrPart = variables.lookup_attribute_key
        ? `, ${variables.lookup_attribute_key}=${variables.lookup_attribute_value}`
        : "";
      const description = `CloudTrail (${variables.start_time} → ${variables.end_time}${attrPart})`;
      setEvents(data.events, description);
    },
  });
}
