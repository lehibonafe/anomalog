import { useTestConnection } from "../../hooks/useTestConnection";
import type { LlmProvider } from "../../state/selectionStore";
import { useSelectionStore } from "../../state/selectionStore";

const PROVIDER_MODEL_PLACEHOLDER: Record<LlmProvider, string> = {
  gemini: "gemini-2.5-flash",
  openai: "gpt-4o-mini",
  anthropic: "claude-haiku-4-5-20251001",
  ollama: "llama3.1",
  litellm: "qwen3:4b",
};

export function ModelSettingsPanel() {
  const llmProvider = useSelectionStore((s) => s.llmProvider);
  const setLlmProvider = useSelectionStore((s) => s.setLlmProvider);
  const llmApiKey = useSelectionStore((s) => s.llmApiKey);
  const setLlmApiKey = useSelectionStore((s) => s.setLlmApiKey);
  const llmModel = useSelectionStore((s) => s.llmModel);
  const setLlmModel = useSelectionStore((s) => s.setLlmModel);
  const llmBaseUrl = useSelectionStore((s) => s.llmBaseUrl);
  const setLlmBaseUrl = useSelectionStore((s) => s.setLlmBaseUrl);
  const testConnection = useTestConnection();

  return (
    <div className="model-settings-panel">
      <label className="model-settings-field">
        Provider
        <select
          value={llmProvider}
          onChange={(e) => setLlmProvider(e.target.value as LlmProvider)}
        >
          <option value="gemini">Gemini</option>
          <option value="openai">OpenAI</option>
          <option value="anthropic">Anthropic</option>
          <option value="ollama">Ollama (local)</option>
          <option value="litellm">LiteLLM (proxy)</option>
        </select>
      </label>

      <label className="model-settings-field">
        {llmProvider === "ollama" ? "API key (usually not required)" : "API key"}
        <input
          type="password"
          placeholder={
            llmProvider === "gemini" || llmProvider === "litellm"
              ? "Uses server default if blank"
              : "Required"
          }
          value={llmApiKey}
          onChange={(e) => setLlmApiKey(e.target.value)}
          autoComplete="off"
        />
      </label>

      <label className="model-settings-field">
        Model
        <input
          type="text"
          placeholder={`e.g. ${PROVIDER_MODEL_PLACEHOLDER[llmProvider]} (default if blank)`}
          value={llmModel}
          onChange={(e) => setLlmModel(e.target.value)}
        />
      </label>

      {llmProvider === "ollama" && (
        <label className="model-settings-field">
          Base URL
          <input
            type="text"
            placeholder="http://localhost:11434/v1"
            value={llmBaseUrl}
            onChange={(e) => setLlmBaseUrl(e.target.value)}
          />
          {/* If the backend runs in Docker and Ollama runs on the host,
              "localhost" inside the container won't reach the host — use
              host.docker.internal instead. */}
        </label>
      )}

      {llmProvider === "litellm" && (
        <label className="model-settings-field">
          Base URL
          <input
            type="text"
            placeholder="http://llm.etapinc.com/v1 (default if blank)"
            value={llmBaseUrl}
            onChange={(e) => setLlmBaseUrl(e.target.value)}
          />
        </label>
      )}

      <button
        type="button"
        className="btn-block"
        disabled={testConnection.isPending}
        onClick={() => testConnection.mutate()}
      >
        {testConnection.isPending && <span className="spinner" />}
        {testConnection.isPending ? "Testing..." : "Test connection"}
      </button>
      {testConnection.isSuccess && (
        <p className={testConnection.data.success ? "success-text" : "error-text"}>
          {testConnection.data.success
            ? `Connected (model: ${testConnection.data.model})`
            : testConnection.data.message}
        </p>
      )}
      {testConnection.isError && (
        <p className="error-text">Test failed. Check the backend logs.</p>
      )}
    </div>
  );
}
