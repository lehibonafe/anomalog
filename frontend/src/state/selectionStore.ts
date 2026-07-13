import { create } from "zustand";

import type { LogEvent } from "../api/types";

export type SourceMode = "cloudwatch" | "s3";
export type LlmProvider = "gemini" | "openai" | "anthropic" | "ollama";

export interface HighlightedRange {
  start: number;
  end: number;
}

interface SelectionState {
  sourceMode: SourceMode;
  logGroupNames: string[];
  bucket: string | null;
  prefix: string;
  startTime: string;
  endTime: string;
  filterPattern: string;
  events: LogEvent[];
  sourceDescription: string;
  highlightedRange: HighlightedRange | null;
  llmProvider: LlmProvider;
  llmApiKey: string;
  llmModel: string;
  llmBaseUrl: string;

  setSourceMode: (mode: SourceMode) => void;
  setLogGroupNames: (names: string[]) => void;
  setBucket: (bucket: string | null) => void;
  setPrefix: (prefix: string) => void;
  setTimeRange: (start: string, end: string) => void;
  setFilterPattern: (pattern: string) => void;
  setEvents: (events: LogEvent[], sourceDescription: string) => void;
  setHighlightedRange: (range: HighlightedRange | null) => void;
  setLlmProvider: (provider: LlmProvider) => void;
  setLlmApiKey: (key: string) => void;
  setLlmModel: (model: string) => void;
  setLlmBaseUrl: (url: string) => void;
}

export const useSelectionStore = create<SelectionState>((set) => ({
  sourceMode: "cloudwatch",
  logGroupNames: [],
  bucket: null,
  prefix: "",
  startTime: "",
  endTime: "",
  filterPattern: "",
  events: [],
  sourceDescription: "",
  highlightedRange: null,
  llmProvider: "gemini",
  llmApiKey: "",
  llmModel: "",
  llmBaseUrl: "",

  setSourceMode: (mode) => set({ sourceMode: mode }),
  setLogGroupNames: (names) => set({ logGroupNames: names }),
  setBucket: (bucket) => set({ bucket }),
  setPrefix: (prefix) => set({ prefix }),
  setTimeRange: (start, end) => set({ startTime: start, endTime: end }),
  setFilterPattern: (pattern) => set({ filterPattern: pattern }),
  setEvents: (events, sourceDescription) =>
    set({ events, sourceDescription, highlightedRange: null }),
  setHighlightedRange: (range) => set({ highlightedRange: range }),
  setLlmProvider: (provider) => set({ llmProvider: provider }),
  setLlmApiKey: (key) => set({ llmApiKey: key }),
  setLlmModel: (model) => set({ llmModel: model }),
  setLlmBaseUrl: (url) => set({ llmBaseUrl: url }),
}));
