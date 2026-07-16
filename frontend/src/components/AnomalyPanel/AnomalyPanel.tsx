import { isAxiosError } from "axios";
import { useState } from "react";

import { useAnomalyAnalysis } from "../../hooks/useAnomalyAnalysis";
import { useTestConnection } from "../../hooks/useTestConnection";
import type { LlmProvider } from "../../state/selectionStore";
import { useSelectionStore } from "../../state/selectionStore";
import { FindingCard } from "./FindingCard";

const PROVIDER_MODEL_PLACEHOLDER: Record<LlmProvider, string> = {
  gemini: "gemini-2.5-flash",
  openai: "gpt-4o-mini",
  anthropic: "claude-haiku-4-5-20251001",
  ollama: "llama3.1",
};

export function AnomalyPanel() {
  const events = useSelectionStore((s) => s.events);
  const llmProvider = useSelectionStore((s) => s.llmProvider);
  const setLlmProvider = useSelectionStore((s) => s.setLlmProvider);
  const llmApiKey = useSelectionStore((s) => s.llmApiKey);
  const setLlmApiKey = useSelectionStore((s) => s.setLlmApiKey);
  const llmModel = useSelectionStore((s) => s.llmModel);
  const setLlmModel = useSelectionStore((s) => s.setLlmModel);
  const llmBaseUrl = useSelectionStore((s) => s.llmBaseUrl);
  const setLlmBaseUrl = useSelectionStore((s) => s.setLlmBaseUrl);
  const [userPrompt, setUserPrompt] = useState("");
  const analysis = useAnomalyAnalysis();
  const testConnection = useTestConnection();

  const quotaExceeded =
    analysis.isError && isAxiosError(analysis.error) && analysis.error.response?.status === 429;
  const isCustom = llmProvider !== "gemini" || !!llmApiKey || !!llmModel || !!llmBaseUrl;

  return (
    <div className="anomaly-panel">
      <div className="panel-section-title">Anomaly analysis</div>

      <details className="model-settings">
        <summary>Model settings {isCustom ? "(custom)" : "(default)"}</summary>

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
          </select>
        </label>

        <label className="model-settings-field">
          {llmProvider === "ollama" ? "API key (usually not required)" : "API key"}
          <input
            type="password"
            placeholder={llmProvider === "gemini" ? "Uses server default if blank" : "Required"}
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
      </details>

      <label className="model-settings-field">
        Prompt (optional)
        <textarea
          className="analysis-prompt"
          placeholder="What should the LLM look for? Blank = scan for errors and anomalies"
          value={userPrompt}
          onChange={(e) => setUserPrompt(e.target.value)}
          rows={3}
        />
      </label>

      <button
        type="button"
        className="btn-primary btn-block"
        disabled={events.length === 0 || analysis.isPending}
        onClick={() => analysis.mutate(userPrompt)}
      >
        {analysis.isPending && <span className="spinner" />}
        {analysis.isPending
          ? "Analyzing..."
          : userPrompt.trim()
            ? "Analyze with prompt"
            : "Analyze logs"}
      </button>

      {quotaExceeded && (
        <p className="error-text">
          Rate limit exceeded before any log chunks could be analyzed. Wait a bit or narrow
          the time range, then retry.
        </p>
      )}
      {analysis.isError && !quotaExceeded && (
        <p className="error-text">Analysis failed. Check the backend logs.</p>
      )}

      {analysis.data && (
        <>
          <div className="stats-row">
            <span className="stat-badge">
              {analysis.data.lines_considered}/{events.length} lines analyzed
            </span>
            <span className="stat-badge">
              {analysis.data.lines_skipped_by_prefilter} skipped by prefilter
            </span>
            <span className="stat-badge">
              {analysis.data.chunks_analyzed}/{analysis.data.chunks_total} chunks
            </span>
            <span className="stat-badge">{analysis.data.model}</span>
          </div>
          {analysis.data.warnings.map((w, i) => (
            <p key={i} className="warning-text">
              {w}
            </p>
          ))}
          {analysis.data.findings.length === 0 && (
            <p className="hint">No findings for this slice.</p>
          )}
          <div className="finding-list">
            {analysis.data.findings.map((f) => (
              <FindingCard key={f.id} finding={f} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
