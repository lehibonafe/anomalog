import { apiClient } from "./client";
import type {
  CloudWatchSearchRequest,
  CloudWatchSearchResponse,
  AppConfig,
  LogGroupsResponse,
} from "./types";

export async function fetchLogGroups(
  keyword?: string,
  nextToken?: string
): Promise<LogGroupsResponse> {
  const { data } = await apiClient.get<LogGroupsResponse>("/api/cloudwatch/log-groups", {
    params: { keyword: keyword || undefined, next_token: nextToken },
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

export async function fetchAppConfig(): Promise<AppConfig> {
  const { data } = await apiClient.get<AppConfig>("/api/config");
  return data;
}
