export type LogSource = "cloudwatch" | "cloudtrail";

export interface LogEvent {
  source: LogSource;
  origin: string;
  stream_or_key: string;
  timestamp: string | null;
  message: string;
  line_index: number;
}

export interface LogGroup {
  name: string;
  identifier: string;
  account_id: string | null;
  stored_bytes: number | null;
  creation_time: string | null;
}

export interface LogGroupsResponse {
  log_groups: LogGroup[];
  next_token: string | null;
}

export interface CloudWatchSearchRequest {
  log_group_names: string[];
  start_time: string;
  end_time: string;
  filter_pattern?: string | null;
  limit?: number;
  cursor?: string | null;
}

export interface CloudWatchSearchResponse {
  events: LogEvent[];
  cursor: string | null;
  truncated: boolean;
  total_returned: number;
}

export type LiveTailServerMessage =
  | {
      type: "session_started";
      inactivity_timeout_seconds: number;
      cost_per_minute_usd: number;
      free_tier_minutes: number;
    }
  | { type: "events"; events: LogEvent[]; sampled: boolean }
  | { type: "session_stopped" | "session_ended"; reason: string }
  | { type: "error"; message: string };

export interface AppConfig {
  cloudtrail_account_filter_available: boolean;
  live_tail_max_concurrent_sessions: number;
  live_tail_inactivity_timeout_seconds: number;
  live_tail_cost_per_minute_usd: number;
  live_tail_free_tier_minutes: number;
}

export type CloudTrailLookupAttributeKey =
  | "EventId"
  | "EventName"
  | "ReadOnly"
  | "Username"
  | "ResourceType"
  | "ResourceName"
  | "EventSource"
  | "AccessKeyId";

export type CloudTrailAccountId =
  | "887350548529"
  | "065031412132"
  | "221315724874"
  | "550222016520"
  | "679437835821"
  | "765186506449";

export interface CloudTrailSearchRequest {
  start_time: string;
  end_time: string;
  account_id?: CloudTrailAccountId | null;
  lookup_attribute_key?: CloudTrailLookupAttributeKey | null;
  lookup_attribute_value?: string | null;
  limit?: number;
  cursor?: string | null;
}

export interface CloudTrailSearchResponse {
  events: LogEvent[];
  cursor: string | null;
  truncated: boolean;
  total_returned: number;
}

export type LlmProviderName = "gemini" | "openai" | "anthropic" | "ollama" | "litellm";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

export interface AnalysisRequest {
  events: LogEvent[];
  context: { source_description: string };
  provider?: LlmProviderName;
  api_key?: string | null;
  model?: string | null;
  base_url?: string | null;
  user_prompt?: string | null;
  history?: ChatMessage[];
}

export interface TestConnectionRequest {
  provider?: LlmProviderName;
  api_key?: string | null;
  model?: string | null;
  base_url?: string | null;
}

export interface TestConnectionResponse {
  success: boolean;
  message: string;
  model: string;
}

export interface AnalysisResponse {
  analysis: string;
  chunks_analyzed: number;
  chunks_total: number;
  lines_submitted: number;
  lines_analyzed: number;
  lines_sent_to_model?: number;
  lines_collapsed_as_duplicates?: number;
  lines_omitted_by_limits: number;
  lines_not_analyzed: number;
  lines_shortened: number;
  lines_considered: number;
  lines_skipped_by_prefilter: number;
  history_messages_omitted?: number;
  estimated_input_tokens?: number;
  model: string;
  warnings: string[];
}
