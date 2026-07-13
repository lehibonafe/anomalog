import { apiClient } from "./client";
import type {
  S3BucketsResponse,
  S3ContentRequest,
  S3ContentResponse,
  S3ObjectsResponse,
} from "./types";

export async function fetchBuckets(): Promise<S3BucketsResponse> {
  const { data } = await apiClient.get<S3BucketsResponse>("/api/s3/buckets");
  return data;
}

export async function listS3Objects(params: {
  bucket: string;
  prefix?: string;
  start?: string;
  end?: string;
  continuationToken?: string;
}): Promise<S3ObjectsResponse> {
  const { data } = await apiClient.get<S3ObjectsResponse>("/api/s3/objects", {
    params: {
      bucket: params.bucket,
      prefix: params.prefix || undefined,
      start: params.start || undefined,
      end: params.end || undefined,
      continuation_token: params.continuationToken || undefined,
    },
  });
  return data;
}

export async function fetchS3Content(
  request: S3ContentRequest
): Promise<S3ContentResponse> {
  const { data } = await apiClient.post<S3ContentResponse>(
    "/api/s3/objects/content",
    request
  );
  return data;
}
