import { useMutation, useQuery } from "@tanstack/react-query";

import { fetchBuckets, fetchS3Content, listS3Objects } from "../api/s3";
import { useSelectionStore } from "../state/selectionStore";

export function useBuckets() {
  return useQuery({
    queryKey: ["s3-buckets"],
    queryFn: () => fetchBuckets(),
  });
}

export function useS3Objects(params: {
  bucket: string | null;
  prefix: string;
  start?: string;
  end?: string;
}) {
  return useQuery({
    queryKey: ["s3-objects", params.bucket, params.prefix, params.start, params.end],
    queryFn: () =>
      listS3Objects({
        bucket: params.bucket as string,
        prefix: params.prefix,
        start: params.start,
        end: params.end,
      }),
    enabled: !!params.bucket,
  });
}

export function useS3Content() {
  const setEvents = useSelectionStore((s) => s.setEvents);

  return useMutation({
    mutationFn: (params: { bucket: string; keys: string[] }) => fetchS3Content(params),
    onSuccess: (data, variables) => {
      const description = `S3 s3://${variables.bucket}/ keys: ${variables.keys.join(", ")}`;
      setEvents(data.events, description);
    },
  });
}
