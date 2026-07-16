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

export type CloudTrailLookupAttributeKey =
  | "EventId"
  | "EventName"
  | "ReadOnly"
  | "Username"
  | "ResourceType"
  | "ResourceName"
  | "EventSource"
  | "AccessKeyId";

export interface CloudTrailSearchRequest {
  start_time: string;
  end_time: string;
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

export type FindingSeverity = "critical" | "warning" | "info";
export type FindingCategory = "error" | "stack_trace" | "anomaly" | "pattern";

export interface Finding {
  id: string;
  severity: FindingSeverity;
  category: FindingCategory;
  line_index_start: number;
  line_index_end: number;
  excerpt: string;
  explanation: string;
}

export type LlmProviderName = "gemini" | "openai" | "anthropic" | "ollama";

export interface AnalysisRequest {
  events: LogEvent[];
  context: { source_description: string };
  provider?: LlmProviderName;
  api_key?: string | null;
  model?: string | null;
  base_url?: string | null;
  user_prompt?: string | null;
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
  findings: Finding[];
  chunks_analyzed: number;
  chunks_total: number;
  lines_considered: number;
  lines_skipped_by_prefilter: number;
  model: string;
  warnings: string[];
}
