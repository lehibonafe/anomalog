import { apiClient } from "./client";
import type {
  CloudWatchSearchRequest,
  CloudWatchSearchResponse,
  LogGroupsResponse,
} from "./types";

export async function fetchLogGroups(prefix?: string): Promise<LogGroupsResponse> {
  const { data } = await apiClient.get<LogGroupsResponse>("/api/cloudwatch/log-groups", {
    params: { prefix: prefix || undefined },
  });
  return data;
}

export async function searchCloudWatchLogs(
  request: CloudWatchSearchRequest
): Promise<CloudWatchSearchResponse> {
  const { data } = await apiClient.post<CloudWatchSearchResponse>(
    "/api/cloudwatch/logs/search",
    request
  );
  return data;
}
