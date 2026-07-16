import { apiClient } from "./client";
import type {
  AnalysisRequest,
  AnalysisResponse,
  TestConnectionRequest,
  TestConnectionResponse,
} from "./types";

export async function runAnomalyAnalysis(
  request: AnalysisRequest
): Promise<AnalysisResponse> {
  const { data } = await apiClient.post<AnalysisResponse>(
    "/api/analysis/anomalies",
    request
  );
  return data;
}

export async function testLlmConnection(
  request: TestConnectionRequest
): Promise<TestConnectionResponse> {
  const { data } = await apiClient.post<TestConnectionResponse>(
    "/api/analysis/test-connection",
    request
  );
  return data;
}
