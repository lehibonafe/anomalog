import { useInfiniteQuery } from "@tanstack/react-query";

import { fetchLogGroups } from "../api/cloudwatch";

export function useLogGroups(keyword: string) {
  return useInfiniteQuery({
    queryKey: ["log-groups", keyword],
    queryFn: ({ pageParam }) => fetchLogGroups(keyword, pageParam),
    initialPageParam: undefined as string | undefined,
    getNextPageParam: (lastPage) => lastPage.next_token ?? undefined,
  });
}
