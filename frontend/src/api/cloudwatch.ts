import { apiClient } from "./client";
import type {
  CloudWatchSearchRequest,
  CloudWatchSearchResponse,
  LiveTailConfig,
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

export function cloudWatchLiveTailUrl(): string {
  const configuredBase = apiClient.defaults.baseURL ?? window.location.origin;
  const apiBase = new URL(configuredBase, window.location.origin);
  const url = new URL("/api/cloudwatch/logs/live-tail", apiBase);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

export async function fetchLiveTailConfig(): Promise<LiveTailConfig> {
  const { data } = await apiClient.get<LiveTailConfig>("/api/config");
  return data;
}
