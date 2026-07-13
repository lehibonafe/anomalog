import { useQuery } from "@tanstack/react-query";

import { fetchLogGroups } from "../api/cloudwatch";

export function useLogGroups(prefix: string) {
  return useQuery({
    queryKey: ["log-groups", prefix],
    queryFn: () => fetchLogGroups(prefix),
  });
}
