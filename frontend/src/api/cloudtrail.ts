import { apiClient } from "./client";
import type { CloudTrailSearchRequest, CloudTrailSearchResponse } from "./types";

export async function searchCloudTrailEvents(
  request: CloudTrailSearchRequest
): Promise<CloudTrailSearchResponse> {
  const { data } = await apiClient.post<CloudTrailSearchResponse>(
    "/api/cloudtrail/events/search",
    request
  );
  return data;
}
