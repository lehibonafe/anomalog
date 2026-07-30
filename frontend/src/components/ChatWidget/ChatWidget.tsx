import { isAxiosError } from "axios";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import type { AnalysisResponse, ChatMessage } from "../../api/types";
import { useAnomalyAnalysis } from "../../hooks/useAnomalyAnalysis";
import { useSelectionStore } from "../../state/selectionStore";
import { AnalysisResult } from "./AnalysisResult";
import { ModelSettingsPanel } from "./ModelSettingsPanel";

interface ChatTurn {
  id: number;
  role: "user" | "assistant";
  content: string;
  isError?: boolean;
  stats?: Pick<
    AnalysisResponse,
    "chunks_analyzed" | "chunks_total" | "lines_considered" | "lines_skipped_by_prefilter" | "model" | "warnings"
  >;
}

let nextTurnId = 0;

function errorMessage(error: unknown): string {
  if (isAxiosError(error) && error.response?.status === 429) {
    return "Rate limit exceeded before any log chunks could be analyzed. Wait a bit or narrow the time range, then retry.";
  }
  return "Analysis failed. Check the backend logs.";
}

export function ChatWidget() {
  const events = useSelectionStore((s) => s.events);
  const llmProvider = useSelectionStore((s) => s.llmProvider);
  const llmApiKey = useSelectionStore((s) => s.llmApiKey);
  const llmModel = useSelectionStore((s) => s.llmModel);
  const llmBaseUrl = useSelectionStore((s) => s.llmBaseUrl);
  const isCustomModel = llmProvider !== "litellm" || !!llmApiKey || !!llmModel || !!llmBaseUrl;

  const [isOpen, setIsOpen] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [messages, setMessages] = useState<ChatTurn[]>([]);
  const [input, setInput] = useState("");
  const analysis = useAnomalyAnalysis();
  const autoScanFired = useRef(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // A new search means a new log slice — the running conversation no longer applies.
  useEffect(() => {
    autoScanFired.current = false;
    setMessages([]);
  }, [events]);

  useEffect(() => {
    if (!isOpen || events.length === 0 || autoScanFired.current) return;
    autoScanFired.current = true;
    analysis.mutate(
      { userPrompt: "", history: [] },
      {
        onSuccess: (data) => {
          setMessages([
            {
              id: nextTurnId++,
              role: "assistant",
              content: data.analysis.trim() || "No noteworthy problems were detected.",
              stats: data,
            },
          ]);
        },
        onError: (error) => {
          setMessages([
            { id: nextTurnId++, role: "assistant", isError: true, content: errorMessage(error) },
          ]);
        },
      }
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, events]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ block: "end" });
  }, [messages, analysis.isPending]);

  function handleSend() {
    const text = input.trim();
    if (!text || analysis.isPending) return;

    const history: ChatMessage[] = messages
      .filter((m) => !m.isError)
      .map((m) => ({ role: m.role, content: m.content }));

    setMessages((prev) => [...prev, { id: nextTurnId++, role: "user", content: text }]);
    setInput("");

    analysis.mutate(
      { userPrompt: text, history },
      {
        onSuccess: (data) => {
          setMessages((prev) => [
            ...prev,
            {
              id: nextTurnId++,
              role: "assistant",
              content: data.analysis.trim() || "No analysis text for this slice.",
            },
          ]);
        },
        onError: (error) => {
          setMessages((prev) => [
            ...prev,
            { id: nextTurnId++, role: "assistant", isError: true, content: errorMessage(error) },
          ]);
        },
      }
    );
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <>
      {isOpen && (
        <div className="chat-panel">
          <div className="chat-panel-header">
            <span className="chat-panel-title">Log assistant</span>
            <div className="chat-panel-header-actions">
              <button
                type="button"
                className="icon-button"
                aria-label="Model settings"
                aria-expanded={showSettings}
                onClick={() => setShowSettings((v) => !v)}
              >
                ⚙
              </button>
              <button
                type="button"
                className="icon-button"
                aria-label="Close chat"
                onClick={() => setIsOpen(false)}
              >
                ✕
              </button>
            </div>
          </div>

          {showSettings && (
            <div className="chat-settings">
              <div className="chat-settings-label">
                Model settings {isCustomModel ? "(custom)" : "(default)"}
              </div>
              <ModelSettingsPanel />
            </div>
          )}

          <div className="chat-messages">
            {events.length === 0 ? (
              <p className="hint chat-empty-hint">
                Load logs from the sidebar to start a conversation.
              </p>
            ) : messages.length === 0 && !analysis.isPending ? (
              <p className="hint chat-empty-hint">Ready to scan {events.length} lines.</p>
            ) : (
              messages.map((m) => (
                <div key={m.id} className={`chat-bubble chat-bubble-${m.role}`}>
                  {m.isError ? (
                    <p className="error-text">{m.content}</p>
                  ) : m.role === "assistant" ? (
                    <AnalysisResult text={m.content} className="chat-bubble-text" />
                  ) : (
                    <p className="chat-bubble-text">{m.content}</p>
                  )}
                  {m.stats && (
                    <div className="stats-row">
                      <span className="stat-badge">
                        {m.stats.lines_considered}/{events.length} lines analyzed
                      </span>
                      <span className="stat-badge">
                        {m.stats.lines_skipped_by_prefilter} skipped by prefilter
                      </span>
                      <span className="stat-badge">
                        {m.stats.chunks_analyzed}/{m.stats.chunks_total} chunks
                      </span>
                      <span className="stat-badge">{m.stats.model}</span>
                    </div>
                  )}
                  {m.stats?.warnings.map((w, i) => (
                    <p key={i} className="warning-text">
                      {w}
                    </p>
                  ))}
                </div>
              ))
            )}
            {analysis.isPending && (
              <div className="chat-bubble chat-bubble-assistant chat-bubble-pending">
                <span className="spinner dark" />
                Analyzing...
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="chat-input-row">
            <textarea
              placeholder={events.length === 0 ? "Load logs to chat" : "Ask a follow-up question..."}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={events.length === 0 || analysis.isPending}
              rows={1}
            />
            <button
              type="button"
              className="btn-primary chat-send-button"
              disabled={events.length === 0 || analysis.isPending || !input.trim()}
              onClick={handleSend}
            >
              Send
            </button>
          </div>
        </div>
      )}

      <button
        type="button"
        className="chat-fab"
        aria-label={isOpen ? "Close log assistant" : "Open log assistant"}
        onClick={() => setIsOpen((v) => !v)}
      >
        <svg
          viewBox="0 0 24 24"
          width="22"
          height="22"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
        </svg>
      </button>
    </>
  );
}
