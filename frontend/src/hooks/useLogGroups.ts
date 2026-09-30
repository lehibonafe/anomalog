import { useInfiniteQuery } from "@tanstack/react-query";

import { fetchLogGroups } from "../api/cloudwatch";

export function useLogGroups(prefix: string) {
  return useInfiniteQuery({
    queryKey: ["log-groups", prefix],
    queryFn: ({ pageParam }) => fetchLogGroups(prefix, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_token ?? undefined,
  });
}
