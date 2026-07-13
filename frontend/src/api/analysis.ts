import { apiClient } from "./client";
import type { AnalysisRequest, AnalysisResponse } from "./types";

export async function runAnomalyAnalysis(
  request: AnalysisRequest
): Promise<AnalysisResponse> {
  const { data } = await apiClient.post<AnalysisResponse>(
    "/api/analysis/anomalies",
    request
  );
  return data;
}
