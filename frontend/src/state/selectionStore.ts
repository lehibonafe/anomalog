import { create } from "zustand";

import type { CloudTrailAccountId, CloudTrailLookupAttributeKey, CloudTrailSearchRequest, CloudWatchSearchRequest, LogEvent } from "../api/types";

export type SourceMode = "cloudwatch" | "cloudtrail";
export type LlmProvider = "gemini" | "openai" | "anthropic" | "ollama" | "litellm";

export const DEFAULT_LLM_MODELS: Record<LlmProvider, string> = {
  gemini: "gemini-3.8-flash",
  openai: "gpt-6-sol",
  anthropic: "claude-sonnet-5",
  ollama: "qwen3.5:9b",
  litellm: "qwen3.8-flash",
};

export interface HighlightedRange {
  start: number;
  end: number;
  ranges?: Array<{ start: number; end: number }>;
}

interface SelectionState {
  sourceMode: SourceMode;
  logGroupNames: string[];
  startTime: string;
  endTime: string;
  filterPattern: string;
  cloudTrailAccountId: CloudTrailAccountId | "";
  cloudTrailAttributeKey: CloudTrailLookupAttributeKey | "";
  cloudTrailAttributeValue: string;
  events: LogEvent[];
  sourceDescription: string;
  highlightedRange: HighlightedRange | null;
  cloudWatchNextRequest: CloudWatchSearchRequest | null;
  cloudTrailNextRequest: CloudTrailSearchRequest | null;
  llmProvider: LlmProvider;
  llmApiKey: string;
  llmModel: string;
  llmBaseUrl: string;

  setSourceMode: (mode: SourceMode) => void;
  setLogGroupNames: (names: string[]) => void;
  setTimeRange: (start: string, end: string) => void;
  setFilterPattern: (pattern: string) => void;
  setCloudTrailAccountId: (accountId: CloudTrailAccountId | "") => void;
  setCloudTrailAttributeKey: (key: CloudTrailLookupAttributeKey | "") => void;
  setCloudTrailAttributeValue: (value: string) => void;
  setEvents: (events: LogEvent[], sourceDescription: string) => void;
  appendEvents: (events: LogEvent[]) => void;
  setHighlightedRange: (range: HighlightedRange | null) => void;
  setCloudWatchNextRequest: (request: CloudWatchSearchRequest | null) => void;
  setCloudTrailNextRequest: (request: CloudTrailSearchRequest | null) => void;
  setLlmProvider: (provider: LlmProvider) => void;
  setLlmApiKey: (key: string) => void;
  setLlmModel: (model: string) => void;
  setLlmBaseUrl: (url: string) => void;
}

export const useSelectionStore = create<SelectionState>((set, get) => ({
  sourceMode: "cloudwatch",
  logGroupNames: [],
  startTime: "",
  endTime: "",
  filterPattern: "",
  cloudTrailAccountId: "",
  cloudTrailAttributeKey: "",
  cloudTrailAttributeValue: "",
  events: [],
  sourceDescription: "",
  highlightedRange: null,
  cloudWatchNextRequest: null,
  cloudTrailNextRequest: null,
  llmProvider: "litellm",
  llmApiKey: "",
  llmModel: "",
  llmBaseUrl: "",

  setSourceMode: (mode) => set({ sourceMode: mode }),
  setLogGroupNames: (names) => set({ logGroupNames: names }),
  setTimeRange: (start, end) => set({ startTime: start, endTime: end }),
  setFilterPattern: (pattern) => set({ filterPattern: pattern }),
  setCloudTrailAccountId: (accountId) => set({ cloudTrailAccountId: accountId }),
  setCloudTrailAttributeKey: (key) => set({ cloudTrailAttributeKey: key }),
  setCloudTrailAttributeValue: (value) => set({ cloudTrailAttributeValue: value }),
  setEvents: (events, sourceDescription) =>
    set({
      events,
      sourceDescription,
      highlightedRange: null,
      cloudWatchNextRequest: null,
      cloudTrailNextRequest: null,
    }),
  appendEvents: (newEvents) => {
    const offset = get().events.length;
    const reindexed = newEvents.map((e) => ({ ...e, line_index: e.line_index + offset }));
    set((state) => ({ events: [...state.events, ...reindexed] }));
  },
  setHighlightedRange: (range) => set({ highlightedRange: range }),
  setCloudWatchNextRequest: (request) => set({ cloudWatchNextRequest: request }),
  setCloudTrailNextRequest: (request) => set({ cloudTrailNextRequest: request }),
  setLlmProvider: (provider) => set({ llmProvider: provider, llmModel: "" }),
  setLlmApiKey: (key) => set({ llmApiKey: key }),
  setLlmModel: (model) => set({ llmModel: model }),
  setLlmBaseUrl: (url) => set({ llmBaseUrl: url }),
}));
