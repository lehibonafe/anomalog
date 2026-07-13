import { useMutation } from "@tanstack/react-query";

import { runAnomalyAnalysis } from "../api/analysis";
import type { AnalysisResponse } from "../api/types";
import { useSelectionStore } from "../state/selectionStore";

export function useAnomalyAnalysis() {
  const events = useSelectionStore((s) => s.events);
  const sourceDescription = useSelectionStore((s) => s.sourceDescription);
  const llmProvider = useSelectionStore((s) => s.llmProvider);
  const llmApiKey = useSelectionStore((s) => s.llmApiKey);
  const llmModel = useSelectionStore((s) => s.llmModel);
  const llmBaseUrl = useSelectionStore((s) => s.llmBaseUrl);

  return useMutation<AnalysisResponse, Error, string>({
    mutationFn: (userPrompt) =>
      runAnomalyAnalysis({
        events,
        context: { source_description: sourceDescription || "Selected log slice" },
        provider: llmProvider,
        api_key: llmApiKey.trim() || null,
        model: llmModel.trim() || null,
        base_url: llmBaseUrl.trim() || null,
        user_prompt: userPrompt.trim() || null,
      }),
  });
}
