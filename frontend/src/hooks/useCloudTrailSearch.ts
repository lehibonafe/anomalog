import { useMutation } from "@tanstack/react-query";

import { searchCloudTrailEvents } from "../api/cloudtrail";
import type { CloudTrailSearchRequest } from "../api/types";
import { useSelectionStore } from "../state/selectionStore";

export function useCloudTrailSearch() {
  const setEvents = useSelectionStore((s) => s.setEvents);
  const appendEvents = useSelectionStore((s) => s.appendEvents);
  const setCloudTrailNextRequest = useSelectionStore((s) => s.setCloudTrailNextRequest);

  return useMutation({
    mutationFn: (request: CloudTrailSearchRequest) => searchCloudTrailEvents(request),
    onMutate: (variables) => {
      if (!variables.cursor) setCloudTrailNextRequest(null);
    },
    onSuccess: (data, variables) => {
      if (variables.cursor) {
        appendEvents(data.events);
      } else {
        const accountPart = variables.account_id
          ? `, account=${variables.account_id}`
          : ", all accounts";
        const attrPart = variables.lookup_attribute_key
          ? `, ${variables.lookup_attribute_key}=${variables.lookup_attribute_value}`
          : "";
        const description = `CloudTrail (${variables.start_time} → ${variables.end_time}${accountPart}${attrPart})`;
        setEvents(data.events, description);
      }

      setCloudTrailNextRequest(data.cursor ? { ...variables, cursor: data.cursor } : null);
    },
  });
}
