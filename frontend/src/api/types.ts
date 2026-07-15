export type LogSource = "cloudwatch" | "s3" | "cloudtrail";

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

export interface S3Bucket {
  name: string;
  creation_date: string | null;
}

export interface S3BucketsResponse {
  buckets: S3Bucket[];
}

export interface S3Object {
  key: string;
  size: number;
  last_modified: string;
}

export interface S3ObjectsResponse {
  objects: S3Object[];
  continuation_token: string | null;
}

export interface S3ContentRequest {
  bucket: string;
  keys: string[];
}

export interface S3ObjectContentInfo {
  key: string;
  byte_size: number;
  truncated: boolean;
  line_count: number;
}

export interface S3ContentResponse {
  events: LogEvent[];
  objects: S3ObjectContentInfo[];
  truncated_overall: boolean;
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

export interface AnalysisResponse {
  findings: Finding[];
  chunks_analyzed: number;
  chunks_total: number;
  lines_considered: number;
  lines_skipped_by_prefilter: number;
  model: string;
  warnings: string[];
}
