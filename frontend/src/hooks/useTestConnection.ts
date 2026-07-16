import { useMutation } from "@tanstack/react-query";

import { testLlmConnection } from "../api/analysis";
import type { TestConnectionResponse } from "../api/types";
import { useSelectionStore } from "../state/selectionStore";

export function useTestConnection() {
  const llmProvider = useSelectionStore((s) => s.llmProvider);
  const llmApiKey = useSelectionStore((s) => s.llmApiKey);
  const llmModel = useSelectionStore((s) => s.llmModel);
  const llmBaseUrl = useSelectionStore((s) => s.llmBaseUrl);

  return useMutation<TestConnectionResponse, Error, void>({
    mutationFn: () =>
      testLlmConnection({
        provider: llmProvider,
        api_key: llmApiKey.trim() || null,
        model: llmModel.trim() || null,
        base_url: llmBaseUrl.trim() || null,
      }),
  });
}
