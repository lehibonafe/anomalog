import { create } from "zustand";

import type { CloudTrailAccountId, CloudTrailLookupAttributeKey, CloudTrailSearchRequest, CloudWatchSearchRequest, LogEvent } from "../api/types";

export type SourceMode = "cloudwatch" | "cloudtrail";
export type LlmProvider = "gemini" | "openai" | "anthropic" | "ollama" | "litellm";
export const MAX_LIVE_TAIL_EVENTS = 10_000;

interface ProviderSettings {
  apiKey: string;
  model: string;
  baseUrl: string;
}

const emptyProviderSettings = (): Record<LlmProvider, ProviderSettings> => ({
  gemini: { apiKey: "", model: "", baseUrl: "" },
  openai: { apiKey: "", model: "", baseUrl: "" },
  anthropic: { apiKey: "", model: "", baseUrl: "" },
  ollama: { apiKey: "", model: "", baseUrl: "" },
  litellm: { apiKey: "", model: "", baseUrl: "" },
});

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
  nextLineIndex: number;
  liveTailDroppedEvents: number;
  sourceDescription: string;
  highlightedRange: HighlightedRange | null;
  cloudWatchNextRequest: CloudWatchSearchRequest | null;
  cloudTrailNextRequest: CloudTrailSearchRequest | null;
  searchGeneration: number;
  activeSearchSource: SourceMode | null;
  searchInFlightCount: number;
  llmProvider: LlmProvider;
  providerSettings: Record<LlmProvider, ProviderSettings>;
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
  appendLiveEvents: (events: LogEvent[]) => void;
  beginSearch: (source: SourceMode) => number;
  isCurrentSearch: (generation: number, source: SourceMode) => boolean;
  invalidateSearch: () => void;
  startSearchRequest: () => void;
  finishSearchRequest: () => void;
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
  nextLineIndex: 0,
  liveTailDroppedEvents: 0,
  sourceDescription: "",
  highlightedRange: null,
  cloudWatchNextRequest: null,
  cloudTrailNextRequest: null,
  searchGeneration: 0,
  activeSearchSource: null,
  searchInFlightCount: 0,
  llmProvider: "litellm",
  providerSettings: emptyProviderSettings(),
  llmApiKey: "",
  llmModel: "",
  llmBaseUrl: "",

  setSourceMode: (mode) => set((state) => mode === state.sourceMode ? state : {
    sourceMode: mode,
    events: [],
    nextLineIndex: 0,
    liveTailDroppedEvents: 0,
    sourceDescription: "",
    highlightedRange: null,
    cloudWatchNextRequest: null,
    cloudTrailNextRequest: null,
    searchGeneration: state.searchGeneration + 1,
    activeSearchSource: null,
  }),
  setLogGroupNames: (names) => set({ logGroupNames: names }),
  setTimeRange: (start, end) => set({ startTime: start, endTime: end }),
  setFilterPattern: (pattern) => set({ filterPattern: pattern }),
  setCloudTrailAccountId: (accountId) => set({ cloudTrailAccountId: accountId }),
  setCloudTrailAttributeKey: (key) => set({ cloudTrailAttributeKey: key }),
  setCloudTrailAttributeValue: (value) => set({ cloudTrailAttributeValue: value }),
  setEvents: (events, sourceDescription) =>
    set({
      events: events.map((event, index) => ({ ...event, line_index: index })),
      nextLineIndex: events.length,
      liveTailDroppedEvents: 0,
      sourceDescription,
      highlightedRange: null,
      cloudWatchNextRequest: null,
      cloudTrailNextRequest: null,
    }),
  appendEvents: (newEvents) => set((state) => ({
    events: [...state.events, ...newEvents.map((event, index) => ({ ...event, line_index: state.nextLineIndex + index }))],
    nextLineIndex: state.nextLineIndex + newEvents.length,
  })),
  appendLiveEvents: (newEvents) => set((state) => {
    const combined = [...state.events, ...newEvents.map((event, index) => ({ ...event, line_index: state.nextLineIndex + index }))];
    const overflow = Math.max(0, combined.length - MAX_LIVE_TAIL_EVENTS);
    return {
      events: overflow ? combined.slice(overflow) : combined,
      nextLineIndex: state.nextLineIndex + newEvents.length,
      liveTailDroppedEvents: state.liveTailDroppedEvents + overflow,
    };
  }),
  beginSearch: (source) => {
    const generation = get().searchGeneration + 1;
    set({ searchGeneration: generation, activeSearchSource: source, cloudWatchNextRequest: null, cloudTrailNextRequest: null });
    return generation;
  },
  isCurrentSearch: (generation, source) => {
    const state = get();
    return state.searchGeneration === generation && state.activeSearchSource === source && state.sourceMode === source;
  },
  invalidateSearch: () => set((state) => ({
    searchGeneration: state.searchGeneration + 1,
    activeSearchSource: null,
    cloudWatchNextRequest: null,
    cloudTrailNextRequest: null,
  })),
  startSearchRequest: () => set((state) => ({ searchInFlightCount: state.searchInFlightCount + 1 })),
  finishSearchRequest: () => set((state) => ({ searchInFlightCount: Math.max(0, state.searchInFlightCount - 1) })),
  setHighlightedRange: (range) => set({ highlightedRange: range }),
  setCloudWatchNextRequest: (request) => set({ cloudWatchNextRequest: request }),
  setCloudTrailNextRequest: (request) => set({ cloudTrailNextRequest: request }),
  setLlmProvider: (provider) => set((state) => ({
    llmProvider: provider,
    llmApiKey: state.providerSettings[provider].apiKey,
    llmModel: state.providerSettings[provider].model,
    llmBaseUrl: state.providerSettings[provider].baseUrl,
  })),
  setLlmApiKey: (key) => set((state) => ({
    llmApiKey: key,
    providerSettings: { ...state.providerSettings, [state.llmProvider]: { ...state.providerSettings[state.llmProvider], apiKey: key } },
  })),
  setLlmModel: (model) => set((state) => ({
    llmModel: model,
    providerSettings: { ...state.providerSettings, [state.llmProvider]: { ...state.providerSettings[state.llmProvider], model } },
  })),
  setLlmBaseUrl: (url) => set((state) => ({
    llmBaseUrl: url,
    providerSettings: { ...state.providerSettings, [state.llmProvider]: { ...state.providerSettings[state.llmProvider], baseUrl: url } },
  })),
}));
