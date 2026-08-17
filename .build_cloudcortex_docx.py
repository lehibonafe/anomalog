from __future__ import annotations

import copy
import os
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parent
DOCX = ROOT / "TraceMind_Documentation.docx"
TMP = ROOT / ".TraceMind_Documentation.docx.tmp"

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CP = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC = "http://purl.org/dc/elements/1.1/"
DCT = "http://purl.org/dc/terms/"
XSI = "http://www.w3.org/2001/XMLSchema-instance"

ET.register_namespace("w", W)
ET.register_namespace("r", R)
ET.register_namespace("cp", CP)
ET.register_namespace("dc", DC)
ET.register_namespace("dcterms", DCT)
ET.register_namespace("xsi", XSI)


def qn(ns: str, tag: str) -> str:
    return f"{{{ns}}}{tag}"


def el(parent: ET.Element, tag: str, *, ns: str = W, attrs: dict[str, str] | None = None) -> ET.Element:
    node = ET.SubElement(parent, qn(ns, tag))
    for key, value in (attrs or {}).items():
        node.set(qn(W, key) if ":" not in key else key, value)
    return node


document = ET.Element(qn(W, "document"))
body = el(document, "body")


def run(parent: ET.Element, text: str, *, bold: bool = False, italic: bool = False,
        color: str | None = None, size: int | None = None, font: str | None = None) -> ET.Element:
    r = el(parent, "r")
    if bold or italic or color or size or font:
        rp = el(r, "rPr")
        if bold:
            el(rp, "b")
        if italic:
            el(rp, "i")
        if color:
            el(rp, "color", attrs={"val": color})
        if size:
            el(rp, "sz", attrs={"val": str(size)})
            el(rp, "szCs", attrs={"val": str(size)})
        if font:
            el(rp, "rFonts", attrs={"ascii": font, "hAnsi": font, "cs": font})
    t = el(r, "t")
    if text[:1].isspace() or text[-1:].isspace():
        t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text
    return r


def paragraph(text: str = "", *, style: str = "Normal", align: str | None = None,
              before: int | None = None, after: int | None = 100, keep: bool = False,
              indent: int | None = None, first: int | None = None) -> ET.Element:
    p = el(body, "p")
    pp = el(p, "pPr")
    if style:
        el(pp, "pStyle", attrs={"val": style})
    if align:
        el(pp, "jc", attrs={"val": align})
    if before is not None or after is not None:
        attrs = {}
        if before is not None:
            attrs["before"] = str(before)
        if after is not None:
            attrs["after"] = str(after)
        el(pp, "spacing", attrs=attrs)
    if keep:
        el(pp, "keepNext")
    if indent is not None or first is not None:
        attrs = {}
        if indent is not None:
            attrs["left"] = str(indent)
        if first is not None:
            attrs["firstLine"] = str(first)
        el(pp, "ind", attrs=attrs)
    if text:
        run(p, text)
    return p


def rich(parts: list[tuple[str, dict]], **kwargs) -> ET.Element:
    p = paragraph("", **kwargs)
    for text, opts in parts:
        run(p, text, **opts)
    return p


def heading(text: str, level: int = 1) -> None:
    paragraph(text, style=f"Heading{level}", before=200 if level == 1 else 120, after=80, keep=True)


def bullet(text: str, level: int = 0) -> None:
    p = paragraph("", after=50, indent=360 + level * 360, first=-250)
    run(p, "• ", bold=True, color="2563EB")
    run(p, text)


def numbered(number: int, text: str) -> None:
    p = paragraph("", after=60, indent=420, first=-300)
    run(p, f"{number}. ", bold=True, color="2563EB")
    run(p, text)


def note(label: str, text: str, color: str = "E8F1FB") -> None:
    p = paragraph("", after=120, indent=220)
    pp = p.find(qn(W, "pPr"))
    el(pp, "shd", attrs={"fill": color})
    el(pp, "spacing", attrs={"before": "100", "after": "100"})
    run(p, f"{label}: ", bold=True, color="1F4E79")
    run(p, text)


def code(text: str) -> None:
    for line in text.splitlines() or [""]:
        p = paragraph("", after=0, indent=240)
        pp = p.find(qn(W, "pPr"))
        el(pp, "shd", attrs={"fill": "F3F4F6"})
        run(p, line or " ", font="Consolas", size=18, color="1F2937")
    paragraph("", after=70)


def page_break() -> None:
    p = paragraph("", after=0)
    r = el(p, "r")
    el(r, "br", attrs={"type": "page"})


def table(headers: list[str], rows: list[list[str]], widths: list[int] | None = None) -> None:
    tbl = el(body, "tbl")
    tp = el(tbl, "tblPr")
    el(tp, "tblW", attrs={"w": "0", "type": "auto"})
    borders = el(tp, "tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el(borders, side, attrs={"val": "single", "sz": "4", "space": "0", "color": "CBD5E1"})
    el(tp, "tblCellMar")

    def add_row(values: list[str], header: bool = False) -> None:
        tr = el(tbl, "tr")
        if header:
            trp = el(tr, "trPr")
            el(trp, "tblHeader")
        for i, value in enumerate(values):
            tc = el(tr, "tc")
            tcp = el(tc, "tcPr")
            if widths:
                el(tcp, "tcW", attrs={"w": str(widths[i]), "type": "dxa"})
            if header:
                el(tcp, "shd", attrs={"fill": "1F4E79"})
            elif len(tbl.findall(qn(W, "tr"))) % 2 == 1:
                el(tcp, "shd", attrs={"fill": "F8FAFC"})
            p = el(tc, "p")
            pp = el(p, "pPr")
            el(pp, "spacing", attrs={"before": "45", "after": "45"})
            run(p, value, bold=header, color="FFFFFF" if header else None, size=18)
    add_row(headers, True)
    for row in rows:
        add_row(row)
    paragraph("", after=70)


def toc_field() -> None:
    p = paragraph("", after=100)
    r1 = el(p, "r")
    el(r1, "fldChar", attrs={"fldCharType": "begin", "dirty": "true"})
    r2 = el(p, "r")
    instr = el(r2, "instrText")
    instr.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    instr.text = ' TOC \\o "1-3" \\h \\z \\u '
    r3 = el(p, "r")
    el(r3, "fldChar", attrs={"fldCharType": "separate"})
    run(p, "Update this field in Word to refresh page numbers.", italic=True, color="64748B")
    r4 = el(p, "r")
    el(r4, "fldChar", attrs={"fldCharType": "end"})


# Cover
p = paragraph("CloudCortex", style="Title", align="center", before=1600, after=120)
run(p, "")
p = paragraph("AWS Log Investigation and LLM-Assisted APM", style="Subtitle", align="center", after=220)
p = paragraph("Technical, Operations, API, and User Documentation", align="center", after=500)
run(p, "", size=24)
rich([("Version 2.0", {"bold": True, "color": "1F4E79"})], align="center", after=60)
paragraph("Updated 18 August 2026", align="center", after=60)
paragraph("Covers the current repository working tree", align="center", after=800)
note("Naming", "The application and API identify the product as CloudCortex. The Word file retains its legacy name, TraceMind_Documentation.docx, for continuity.", "EAF2F8")
page_break()

heading("Document Control", 1)
table(
    ["Item", "Value"],
    [
        ["Product", "CloudCortex"],
        ["Document", "Technical, operations, API, and user guide"],
        ["Version / date", "2.0 / 18 August 2026"],
        ["Implementation baseline", "Current repository working tree, including the in-progress analytics dashboard and facet-filtering UI"],
        ["Primary audiences", "Operators, developers, reviewers, and deployment owners"],
    ],
    [2200, 6500],
)
heading("Table of Contents", 1)
toc_field()
for item in [
    "1. Product Overview", "2. Architecture and Data Flow", "3. User Guide",
    "4. Feature Reference", "5. Backend API Reference", "6. AWS Authentication and Permissions",
    "7. Data Masking and Security", "8. LLM Providers and Model Settings",
    "9. Analysis Pipeline and Prompt Safety", "10. Line-Index and Pagination Contracts",
    "11. Frontend State and Rendering", "12. Configuration Reference", "13. Local Development and Docker",
    "14. Remote Deployment", "15. Testing and Verification", "16. Operational Limits and Troubleshooting",
    "Appendix A. Data Models", "Appendix B. Example Requests",
]:
    bullet(item)
page_break()

heading("1. Product Overview", 1)
paragraph("CloudCortex is a local, browser-based investigation workspace for AWS CloudWatch Logs and CloudTrail event history. It combines bounded AWS search, privacy-first masking, an interactive analytics dashboard, a virtualized raw-log viewer, and conversational LLM analysis. The application has no database and does not persist investigations on the backend.")
heading("1.1 Complete Capability Summary", 2)
table(
    ["Area", "Implemented capabilities"],
    [
        ["AWS discovery", "Prefix-filtered CloudWatch log-group listing; multiple log-group selection; CloudTrail event history with optional lookup attributes"],
        ["Time and search", "15-minute, 1-hour, 24-hour, and 7-day presets; custom UTC-backed ranges; future-date and range validation; CloudWatch filter-pattern support"],
        ["Pagination", "CloudWatch multi-group opaque cursors; CloudTrail NextToken continuation; client-side append and line reindexing"],
        ["Analytics", "Error-trend comparison, status distribution, peak-interval selection, and six log-facet families"],
        ["Log inspection", "Keyword and facet filtering, finding filters, severity and field highlighting, embedded JSON expansion, volume histogram, keyboard navigation, and JSON/CSV/text export"],
        ["AI assistance", "Default anomaly scan, conversational follow-ups, history, stop control, clickable evidence citations, five providers, model/base URL overrides, and connection testing"],
        ["Privacy and safety", "External structured masking with batch/fallback logic, broad local regex masking, analysis-endpoint remasking, prompt-injection defenses, CORS, and inbound rate limiting"],
        ["Operations", "Local dual-service startup, Docker Compose hot reload, EC2-oriented deployment script, health/config endpoints, and backend regression tests"],
    ],
    [1900, 6800],
)
heading("1.2 Intended Use", 2)
bullet("Investigate errors, latency clues, retries, dependency failures, access denials, and AWS changes in a selected time window.")
bullet("Correlate application symptoms with CloudTrail activity while keeping audit/security observations separate when no causal evidence exists.")
bullet("Use LLM output as an evidence-linked investigation aid, not as an autonomous remediation system.")
note("Scope", "CloudCortex is local-only and single-user by design. It has no application login, tenant isolation, durable case storage, alerting engine, or automatic action execution.")

heading("2. Architecture and Data Flow", 1)
code("Browser :5173 (React + TypeScript + Vite)\n    |  Axios JSON over HTTP\n    v\nFastAPI :8000\n    |-- boto3 --> CloudWatch Logs / CloudTrail\n    |-- httpx --> optional external PII masking service\n    `-- provider SDKs --> LiteLLM / Gemini / OpenAI / Anthropic / Ollama")
paragraph("The backend is stateless per request except for cached boto3 resources, the cached masking HTTP client, and process-local rate-limit state. Provider client instances are created for each analysis or connection-test request so an API key supplied by one browser request is not retained in a shared provider object.")
heading("2.1 End-to-End Search Flow", 2)
numbered(1, "The operator selects CloudWatch or CloudTrail, chooses the source/filter, and sets a valid time window.")
numbered(2, "The frontend sends a bounded search request to FastAPI through the configured VITE_API_BASE_URL.")
numbered(3, "The backend obtains AWS credentials through boto3's normal credential chain and calls the appropriate AWS API.")
numbered(4, "Messages are masked in page-sized batches before LogEvent objects are returned. The server sorts the page and assigns line_index values in display order.")
numbered(5, "React stores the returned slice in Zustand. TanStack Query owns request lifecycle state. Additional pages are appended and reindexed by the browser.")
numbered(6, "Dashboard cards, facets, the volume chart, and the virtualized raw viewer all derive from the same in-memory LogEvent array.")
heading("2.2 End-to-End Analysis Flow", 2)
numbered(1, "The browser posts the currently loaded events, source description, provider settings, user question, and prior chat history.")
numbered(2, "The backend validates event/history limits and applies local masking again as defense in depth.")
numbered(3, "Default scans prefilter likely-relevant lines; custom questions keep all lines. Both paths truncate, cap, and chunk the selected slice.")
numbered(4, "A per-provider limiter paces calls. Provider errors are normalized, rate limits are retried with backoff, and successful partial results are preserved.")
numbered(5, "The response includes analysis text, counts, model name, and warnings. Bracketed line citations become clickable controls in the UI.")

heading("3. User Guide", 1)
heading("3.1 Start an Investigation", 2)
numbered(1, "Open http://localhost:5173 after starting both services.")
numbered(2, "Choose CloudWatch or CloudTrail in the left sidebar.")
numbered(3, "Select a preset or enter Start and End values. The browser stores ISO timestamps and prevents future dates, Start after End, and ranges longer than seven days.")
numbered(4, "Configure the source-specific filter, then select Search logs or Search events.")
numbered(5, "Use Load more when the response indicates that more matching data is available. The continuation request uses a snapshot of the original query even if sidebar inputs have since changed.")

heading("3.2 CloudWatch Workflow", 2)
bullet("Type a log-group prefix; the query is debounced by 300 ms. Select one or multiple groups, and use Clear to remove the selection.")
bullet("Enter an optional CloudWatch Logs filter pattern such as ERROR or \"timeout\". The expression is sent unchanged to filter_log_events.")
bullet("Search results from all selected groups are merged and ordered by timestamp for the returned page.")
bullet("The source label records group names, time window, and filter text for the loaded investigation.")

heading("3.3 CloudTrail Workflow", 2)
bullet("Leave Attribute set to None to read all event-history records in the time window.")
bullet("Or choose EventId, EventName, ReadOnly, Username, ResourceType, ResourceName, EventSource, or AccessKeyId and provide a matching value.")
bullet("The key and value must either both be present or both be absent before the Search events button is enabled.")

heading("3.4 Explore the Dashboard", 2)
bullet("Error Trends compares heuristic 4xx client errors with 5xx/application errors across twelve time buckets. Select either summary to filter matching raw lines.")
bullet("Peak interval identifies the bucket with the largest combined error count. Selecting it scrolls/highlights the corresponding line-index range.")
bullet("Status shows counts for Succeeded, Started, Failed, Updated, Accepted, Resolved, and Active. Legend buttons toggle raw-log filters.")
bullet("Facets extract Log level, HTTP method, Route, Status, Exception, and Response duration. A facet group can be collapsed, values can be multi-selected, and Clear all removes all facet selections.")
note("Interpretation", "Dashboard counts are regex/field-derived counts within the loaded slice. They are not system-wide rates, percentiles, or a substitute for CloudWatch metrics.")

heading("3.5 Inspect and Export Logs", 2)
bullet("Filter by a case-insensitive keyword. Keyword, active finding, and facets combine to determine the displayed rows.")
bullet("Selected facet values are highlighted with stable colors. Keyword highlighting has the highest display priority, followed by facet, active-finding, and severity highlights.")
bullet("Expand a line to pretty-print a whole-message or embedded JSON object/array. When dynamic text highlighting is active, the row remains in text mode so matched spans stay visible.")
bullet("Use Arrow Up/Down to move focus and Enter/Space to select a single line. The viewer uses react-window v2 with dynamic row heights for large slices.")
bullet("The 96-bucket volume chart shows the filtered time distribution. Hover/focus reveals counts and times; select a bucket to highlight its line range. If facets are selected, bars are colored by the first selected facet family and segments can toggle values.")
bullet("Export the currently filtered rows as JSON, CSV, or plain text. CSV fields are quoted and spreadsheet formula prefixes are neutralized with a leading apostrophe.")

heading("3.6 Use the Log Assistant", 2)
bullet("Open the floating chat button. A new search clears the conversation because previous answers no longer describe the loaded slice.")
bullet("Select Scan for anomalies to run the default error/anomaly workflow. Its response shows lines considered, prefilter skips, chunks completed, model, and warnings.")
bullet("Ask focused follow-up questions in the text box. Enter sends; Shift+Enter inserts a newline. Non-error, non-greeting turns are included as conversation history.")
bullet("Select Stop analysis to abort the browser request. A stopped request is not added as an error message.")
bullet("Select bracketed citations such as [42] or [42-45] to scroll to and highlight the cited log line(s). Basic bold, italic, and inline-code formatting is rendered in responses.")
bullet("Use Model settings to choose a provider, override credentials/model/base URL where supported, and run Test connection before a full analysis.")

heading("4. Feature Reference", 1)
heading("4.1 CloudWatch Log Groups", 2)
paragraph("GET /api/cloudwatch/log-groups wraps describe_log_groups. The backend accepts prefix, next_token, and a 1–50 limit and returns group name, stored bytes, creation time, and AWS next token. The current UI requests the first matching page and does not expose log-group pagination.")
heading("4.2 Multi-Group CloudWatch Search", 2)
paragraph("Because filter_log_events does not merge independently paginated groups, the service queries each active group, merges events, sorts by timestamp, and stores each group's nextToken in one URL-safe base64 JSON cursor. On continuation, only groups represented in the cursor remain active. Per-call AWS limits are capped at 1,000 per group, while the merged response is capped by max_log_search_lines.")
heading("4.3 CloudTrail Event History", 2)
paragraph("The service calls LookupEvents with 50 records per AWS page and continues until the effective client/server limit is reached or AWS returns no NextToken. Results contain the CloudTrailEvent JSON string as message, event name as stream_or_key, and cloudtrail as origin.")
heading("4.4 Analytics and Facet Extraction", 2)
paragraph("Facet extraction reads both structured JSON fields and plain text. Nested objects are flattened with dotted paths. Routes strip query strings and normalize numeric, UUID, and long hexadecimal path segments to /:id. Durations are grouped into <100 ms, 100–500 ms, 500 ms–1 s, 1–5 s, and >5 s. Status accepts 2xx–5xx values; WARNING normalizes to WARN.")
heading("4.5 Finding and Highlight Rules", 2)
table(
    ["Priority", "Patterns", "Display severity"],
    [
        ["Highest", "5xx, ERROR, Exception/Traceback/Panic, Fatal/Critical", "Critical"],
        ["Medium", "4xx, timeout, refused/denied, WARN", "Warning"],
        ["Informational", "3xx", "Info"],
    ],
    [1400, 5000, 2200],
)
heading("4.6 Embedded JSON", 2)
paragraph("The parser first tries the complete trimmed message. If that fails, it scans balanced object/array spans while respecting JSON strings and escape sequences. Only objects and arrays are rendered as structured JSON; scalar values remain plain log text.")
heading("4.7 Export", 2)
paragraph("Exports are produced entirely in the browser from the filtered array. JSON preserves LogEvent fields; CSV includes line_index, timestamp, source, origin, stream_or_key, and message; text uses [timestamp] [origin/stream_or_key] message. Files are named cloudcortex-logs-<ISO timestamp>.<format>.")

heading("5. Backend API Reference", 1)
paragraph("Default base URL: http://localhost:8000. All application endpoints are under /api and use JSON. FastAPI also exposes its generated OpenAPI interface at /docs unless deployment configuration disables it externally.")
table(
    ["Method and path", "Purpose", "Key inputs / outputs"],
    [
        ["GET /api/health", "Liveness check", "Returns {status: ok}"],
        ["GET /api/config", "Safe client-visible configuration", "AWS region, provider configured flags/models, and selected line caps; never returns API keys"],
        ["POST /api/mask/test", "Developer-only local-regex mask check", "lines[] -> masked[]; bypasses AWS and the external masker"],
        ["GET /api/cloudwatch/log-groups", "List CloudWatch log groups", "prefix?, next_token?, limit 1–50 -> groups and next_token"],
        ["POST /api/cloudwatch/logs/search", "Search one or more groups", "group names, time range, filter, limit, cursor -> events, cursor, truncated, total_returned"],
        ["POST /api/cloudtrail/events/search", "Search CloudTrail history", "time range, optional lookup pair, limit, cursor -> events, cursor, truncated, total_returned"],
        ["POST /api/analysis/anomalies", "Analyze or chat about loaded events", "events, context, provider overrides, prompt, history -> analysis and processing metadata"],
        ["POST /api/analysis/test-connection", "Minimal provider diagnostic", "provider overrides -> success, message, effective model; diagnostic failures normally return HTTP 200"],
    ],
    [2500, 2500, 3700],
)
heading("5.1 Search Validation and Errors", 2)
bullet("Both AWS search routes reject a window longer than max_time_range_days with HTTP 400.")
bullet("The requested limit is bounded by max_log_search_lines. Provider/schema validation errors use FastAPI's validation response.")
bullet("Application exceptions use {\"detail\": \"message\"}: 400 for bad requests, 404 for not found, 429 for quota/inbound throttling, and 502 for upstream LLM request failure.")
bullet("The global inbound fixed-window rate limit applies to every HTTP endpoint by client IP.")
heading("5.2 Analysis Response Metadata", 2)
table(
    ["Field", "Meaning"],
    [
        ["analysis", "Plain-language provider output; successful chunk texts are joined with blank lines"],
        ["chunks_analyzed / chunks_total", "Successful chunks and total chunks scheduled after filtering/capping"],
        ["lines_considered", "Events remaining after prefilter/truncation/caps"],
        ["lines_skipped_by_prefilter", "Events removed only by the default anomaly prefilter/sampling step"],
        ["model", "Effective configured or request-overridden model"],
        ["warnings", "Partial quota results and failed-chunk notices"],
    ],
    [2800, 5900],
)

heading("6. AWS Authentication and Permissions", 1)
paragraph("backend/app/core/aws_session.py creates one cached boto3 Session. It passes profile_name only when AWS_PROFILE is non-empty and passes AWS_REGION when configured. An empty AWS_PROFILE injected by Docker is removed so botocore can continue through its normal chain.")
heading("6.1 Credential Options", 2)
bullet("Environment credentials: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and optional AWS_SESSION_TOKEN. Leave AWS_PROFILE blank/unset.")
bullet("Named local profile: configure AWS_PROFILE and mount ~/.aws. Docker Compose mounts it read-only at /root/.aws.")
bullet("AWS compute role: leave AWS_PROFILE unset and attach an EC2 instance role or ECS task role. For Docker on EC2, IMDSv2 commonly needs hop limit 2.")
heading("6.2 Minimum AWS Access", 2)
bullet("CloudWatch Logs: logs:DescribeLogGroups and logs:FilterLogEvents for the intended groups.")
bullet("CloudTrail: cloudtrail:LookupEvents for event history. The deployment verification also calls sts:GetCallerIdentity.")
note("Least privilege", "Scope resources and regions wherever AWS supports it. The application is read-only with respect to AWS logs and does not modify AWS resources.")

heading("7. Data Masking and Security", 1)
heading("7.1 Masking Order", 2)
numbered(1, "AWS search services collect raw message strings.")
numbered(2, "If MASKING_SERVICE_API_KEY is set, messages are sent to /api/mask/structured/ in configurable batches using X-API-Key authentication.")
numbered(3, "Any connection, timeout, HTTP, JSON, or response-shape failure triggers local regex masking for that sub-batch. After the first failed sub-batch, the remainder of the page uses local masking without repeated external timeouts.")
numbered(4, "Masked messages are used to construct UI-visible LogEvent objects and assign line indexes.")
numbered(5, "POST /api/analysis/anomalies applies local masking again because callers can submit raw event arrays directly.")
paragraph("There is no per-request bypass and no unmask/restore path. The UI and every LLM receive masked text.")
heading("7.2 Local Mask Coverage", 2)
table(
    ["Category", "Examples"],
    [
        ["Credentials and tokens", "AWS access keys, JWTs, Bearer/Basic credentials, GitHub/Slack/Stripe/Google tokens, contextual password/key/token fields, private-key blocks"],
        ["Connection material", "Database URL passwords, connection strings/URLs, sensitive URL query parameters"],
        ["Personal and financial data", "Email, SSN, phone, Luhn-valid payment cards, IBAN, names, DOB/age, address, passport/license/tax/bank/insurance/medical identifiers via contextual fields"],
        ["Network and cloud identifiers", "IPv4, IPv6, MAC address, AWS account IDs, account components in ARNs, location/device identifiers via contextual fields"],
    ],
    [2400, 6300],
)
paragraph("Matches become ***MASKED***. Database URLs preserve scheme, user, host, and database while replacing only the password. ARN/account patterns preserve the surrounding ARN structure.")
heading("7.3 Security Boundary", 2)
bullet("The application has no authentication or authorization. Restrict 5173 and 8000 at the security group, firewall, VPN, or authenticated reverse proxy.")
bullet("CORS limits browser origins but is not authentication. Keep CORS_ORIGINS aligned with the exact URL used to open the frontend.")
bullet("Provider API keys entered in the UI live in in-memory Zustand state, are sent to the backend for that request, and are not deliberately persisted by CloudCortex. Browser/device security still matters.")
bullet("The inbound limiter is an abuse guard only. It is process-local, fixed-window, and keyed by request.client.host; proxies must preserve the intended client identity through trusted configuration outside this app.")
bullet("MASKING_SERVICE_VERIFY_SSL defaults to false because the configured service currently uses a self-signed certificate. This exposes masking traffic to man-in-the-middle risk; enable verification as soon as a trusted certificate is available.")

heading("8. LLM Providers and Model Settings", 1)
table(
    ["Provider", "Default model / endpoint", "Credential behavior", "Rate policy"],
    [
        ["LiteLLM (default)", "qwen3:4b; http://llm.etapinc.com/v1", "LITELLM_API_KEY is required for Settings to boot; request overrides are allowed", "60 RPM, 2 retries"],
        ["Gemini", "gemini-2.5-flash", "Server GEMINI_API_KEY or per-request override", "Configurable; defaults 8 RPM, 2 retries"],
        ["OpenAI", "gpt-4o-mini", "Per-request API key required", "60 RPM, 2 retries"],
        ["Anthropic", "claude-haiku-4-5-20251001", "Per-request API key required", "50 RPM, 2 retries"],
        ["Ollama", "llama3.1; http://localhost:11434/v1", "No real key required; SDK receives a placeholder", "Effectively unpaced at 6000 RPM, no retry"],
    ],
    [1700, 2900, 2600, 1500],
)
paragraph("LiteLLM and Ollama reuse the OpenAI-compatible chat-completions implementation. Gemini uses google-genai and Anthropic uses its messages API. Every client has a 180-second timeout and SDK retries disabled; application-level retry logic is authoritative.")
heading("8.1 Overrides and Connection Test", 2)
bullet("Model can be overridden for all providers. Base URL is exposed in the UI for LiteLLM and Ollama; backend schemas accept it for every provider.")
bullet("Blank Gemini/LiteLLM credentials use server defaults. OpenAI and Anthropic reject a missing key. Ollama normally needs only a reachable base URL.")
bullet("When the backend runs in Docker but Ollama runs on the host, localhost refers to the container; use a host-reachable address such as host.docker.internal where supported.")
bullet("Test connection builds the selected client and submits one minimal log prompt. Expected provider failures are reported in the success/message response rather than raised to the UI.")

heading("9. Analysis Pipeline and Prompt Safety", 1)
heading("9.1 Validation and Preparation", 2)
bullet("Reject more than max_log_search_lines events or max_chat_history_messages prior turns.")
bullet("Remask every message locally, resolve provider defaults/overrides, and build a request-local provider client.")
bullet("Default anomaly scans retain ERROR, WARN, FATAL, exception/traceback/panic/critical, stack-frame, 5xx, timeout, refused, and denied lines plus two surrounding lines. If there are no matches, the service evenly samples the slice.")
bullet("Custom prompts skip the anomaly regex prefilter so lines relevant to the question are not accidentally discarded.")
bullet("Each line is middle-truncated, then recent lines are preferred when line or total-character caps are exceeded.")
bullet("Remaining lines are split into chunk_size_lines and capped by gemini_max_chunks_per_analysis. Despite the legacy setting name, this chunk cap applies to every provider.")
heading("9.2 Provider Calls and Partial Results", 2)
bullet("One process-wide limiter exists per provider because AnomalyService is an lru_cache singleton. Calls are spaced at 60/RPM seconds.")
bullet("Rate-limit signals retry after 5 seconds, then 10 seconds, up to the provider's maximum retry count.")
bullet("If quota is exhausted before the first successful chunk, the API returns HTTP 429. If it occurs later, completed analysis is returned with HTTP 200 and a warning.")
bullet("A non-quota failure skips only that chunk and produces a warning. Successful text is never discarded solely because a later chunk fails.")
heading("9.3 Prompt v4 Guardrails", 2)
bullet("The system role is a senior APM/AWS reliability investigator and must use only supplied logs.")
bullet("It separates observation, correlation, likely cause, and possibility; prohibits invented metrics/topology; and treats filtered slices as samples.")
bullet("It checks traffic, errors, latency, and saturation only where evidence exists; groups repeated symptoms; and distinguishes initiating faults from retries/downstream effects.")
bullet("Log content is explicitly untrusted. Instructions inside logs must not change role, reveal prompts, execute commands, contact systems, or alter output.")
bullet("Factual findings must cite exact supplied line indexes. Ranges are allowed only when every intervening line supports the claim.")
bullet("Severity is evidence-based from INFO through CRITICAL, and recommendations prioritize containment, verification, remediation, and prevention while avoiding destructive or overly broad actions.")
paragraph("The default output uses plain headings—Summary, Key Findings, Likely Impact, Recommended Next Steps, and Evidence Gaps—when relevant. Focused questions may receive a direct shorter response.")

heading("10. Line-Index and Pagination Contracts", 1)
paragraph("line_index is the join key between model evidence and the visible log row. A server response assigns indexes once, in its final timestamp order. The frontend sends the loaded LogEvent array back to analysis without changing its message/index relationship.")
heading("10.1 Loading Additional Pages", 2)
paragraph("Each backend page starts indexing at zero. selectionStore.appendEvents offsets incoming indexes by the number of already loaded events before appending. This creates one continuous browser-visible sequence across pages and preserves clickable LLM citations for the loaded investigation.")
heading("10.2 Invariants for Future Changes", 2)
bullet("Never re-sort messages without reassigning indexes consistently before analysis.")
bullet("Never cite an index found inside message content; only the LogEvent.line_index prefix is authoritative.")
bullet("A new search replaces events and clears highlightedRange, active finding, expanded rows, facet selection, and chat history as appropriate. Load more must append without clearing investigation state.")
bullet("Cursors are opaque client values. Do not parse or modify them outside the backend service that created them.")

heading("11. Frontend State and Rendering", 1)
heading("11.1 State Ownership", 2)
table(
    ["Mechanism", "Responsibilities"],
    [
        ["TanStack Query", "Log-group query, AWS search mutations, analysis mutation, and connection-test mutation; loading/error/result lifecycle"],
        ["Zustand", "Source mode, selections, time/filter values, loaded events, source description, highlighted range, and LLM provider overrides"],
        ["Local React state", "Active dashboard finding, facet selection, keyword, expansion/focus/export format, chat visibility/messages/input, and component hover/collapse state"],
    ],
    [2200, 6500],
)
heading("11.2 Rendering and Accessibility", 2)
bullet("react-window v2 List and useDynamicRowHeight virtualize variable-height expanded rows. v1 FixedSizeList examples are not compatible.")
bullet("Charts, facet values, bucket bars, line references, expand toggles, and major controls use button roles, aria labels/pressed/expanded state, keyboard activation, or focus behavior where implemented.")
bullet("Source changes reset facet selection; genuine new searches reset active findings/expanded rows; pagination deliberately preserves them.")

heading("12. Configuration Reference", 1)
heading("12.1 Backend Environment", 2)
table(
    ["Variable", "Default", "Purpose"],
    [
        ["LITELLM_API_KEY", "required", "Default proxy credential; Settings cannot initialize without a non-empty value"],
        ["LITELLM_MODEL", "qwen3:4b", "Default LiteLLM model"],
        ["LITELLM_BASE_URL", "http://llm.etapinc.com/v1", "OpenAI-compatible proxy base URL"],
        ["GEMINI_API_KEY", "blank", "Optional server Gemini key"],
        ["GEMINI_MODEL", "gemini-2.5-flash", "Default Gemini model"],
        ["GEMINI_RPM_LIMIT", "8", "Gemini pacing"],
        ["GEMINI_MAX_CHUNKS_PER_ANALYSIS", "6", "Maximum chunks for all providers (legacy name)"],
        ["GEMINI_MAX_RETRIES", "2", "Gemini application retries"],
        ["MASKING_SERVICE_URL", "https://pii.etapinc.com", "External masking base URL"],
        ["MASKING_SERVICE_API_KEY", "blank", "Enables external masking and X-API-Key authentication"],
        ["MASKING_SERVICE_MODE", "pipeline", "External structured-mask session category"],
        ["MASKING_SERVICE_TIMEOUT_S", "5.0", "External request timeout"],
        ["MASKING_SERVICE_VERIFY_SSL", "false", "TLS certificate verification; should become true with a trusted certificate"],
        ["MASKING_SERVICE_BATCH_SIZE", "200", "Messages per external structured-mask request"],
        ["AWS_PROFILE", "blank", "Optional named boto3 profile"],
        ["AWS_REGION", "ap-southeast-1", "AWS client region"],
        ["MAX_TIME_RANGE_DAYS", "7", "Server-enforced search-window cap"],
        ["MAX_LOG_SEARCH_LINES", "5000", "Maximum search page/elements accepted for one analysis"],
        ["MAX_CHAT_HISTORY_MESSAGES", "40", "Maximum prior user/assistant messages"],
        ["MAX_ANALYSIS_LINES", "1500", "Line cap after selection"],
        ["MAX_ANALYSIS_CHARS", "500000", "Character cap after truncation"],
        ["MAX_LINE_LENGTH", "2000", "Per-message middle-truncation limit"],
        ["CHUNK_SIZE_LINES", "250", "Events per provider request"],
        ["CORS_ORIGINS", "[http://localhost:5173]", "Allowed browser origins as a JSON list"],
        ["INBOUND_RATE_LIMIT_PER_MINUTE", "120", "Per-client-IP, per-process HTTP request cap"],
    ],
    [3200, 1800, 3700],
)
heading("12.2 Frontend Environment", 2)
table(["Variable", "Default", "Purpose"], [["VITE_API_BASE_URL", "http://localhost:8000", "Browser-visible FastAPI origin; baked/read by Vite"]], [3000, 2300, 3400])
note("Environment changes", "Docker Compose env_file values are loaded when containers are created. Use docker compose up -d (or up -d --build), not only docker compose restart, after changing .env files.")

heading("13. Local Development and Docker", 1)
heading("13.1 Backend", 2)
code("cd backend\npython3 -m venv .venv\nsource .venv/bin/activate\npip install -r requirements.txt\ncp .env.example .env\n# Set LITELLM_API_KEY and AWS access\nuvicorn app.main:app --reload --port 8000")
heading("13.2 Frontend", 2)
code("cd frontend\nnpm install\ncp .env.example .env\nnpm run dev")
paragraph("Open http://localhost:5173. Run ./dev.sh from the repository root to start both processes together; it activates backend/.venv, backgrounds both services, and terminates both on exit.")
heading("13.3 Docker Compose", 2)
code("cp backend/.env.example backend/.env\ncp frontend/.env.example frontend/.env\n# Fill in required values\ndocker compose up --build")
bullet("Backend image: Python 3.12 slim; uvicorn binds 0.0.0.0:8000 with reload; backend/app is bind-mounted.")
bullet("Frontend image: Node 20 slim; Vite binds 0.0.0.0:5173; frontend/src and index.html are bind-mounted.")
bullet("The selective mounts preserve dependencies installed inside images. Compose waits for backend container creation order through depends_on, not application health.")

heading("14. Remote Deployment", 1)
paragraph("deploy.sh targets a Docker Compose host such as EC2. It accepts an explicit IP/DNS name or discovers one through existing frontend configuration, EC2 IMDSv2, then checkip. It creates missing env files, updates VITE_API_BASE_URL and CORS_ORIGINS, rebuilds/recreates containers, checks /api/health, and attempts sts:GetCallerIdentity inside the backend container.")
code("# Preferred: provide the exact address operators will browse\n./deploy.sh <public-ip-or-dns>")
bullet("Restrict ports 5173 and 8000 to the intended operator network. Prefer HTTPS and an authenticated reverse proxy for anything beyond an isolated development environment.")
bullet("Prefer an instance role over static credentials. For container access to EC2 role credentials, configure IMDSv2 response hop limit 2.")
bullet("Set public browser-facing origins exactly, including scheme and port.")
note("Current deployment-script mismatch", "The current deploy.sh checks/prompts for GEMINI_API_KEY, but backend Settings requires LITELLM_API_KEY because LiteLLM is now the default. Set LITELLM_API_KEY in backend/.env before running the script. A Gemini key alone does not satisfy the current boot requirement.", "FFF4CE")

heading("15. Testing and Verification", 1)
heading("15.1 Backend", 2)
code("cd backend\nsource .venv/bin/activate\npython -m pytest tests/")
paragraph("Tests cover AWS range validation, merging/sorting/cursors, CloudTrail lookup attributes, local and external masking/fallback/batching, filter sampling/truncation/chunking, provider registries and SDK error mapping, LiteLLM defaults, prompt v4 guardrails, conversation-history limits, connection diagnostics, rate-limit retries, and partial results. AWS and LLM calls are mocked.")
heading("15.2 Frontend", 2)
code("cd frontend\nnpm run lint\nnpm run build")
paragraph("There is currently no frontend test runner. Lint and production build/type-check are the minimum verification for UI changes. Manually verify keyboard interaction, facet combinations, chart selection, pagination persistence, JSON expansion, export formats, citation scrolling, and chat reset behavior.")
heading("15.3 Smoke Test", 2)
numbered(1, "GET /api/health returns status ok and /api/config exposes only non-secret settings.")
numbered(2, "The browser can list an allowed log group or run a CloudTrail lookup using the configured AWS identity.")
numbered(3, "A known email/token/IP in a test log is masked before display and before analysis.")
numbered(4, "Load more appends with continuous line indexes.")
numbered(5, "The selected LLM provider passes Test connection and a cited response scrolls to the expected row.")

heading("16. Operational Limits and Troubleshooting", 1)
table(
    ["Symptom", "Likely cause / action"],
    [
        ["Backend fails during Settings construction", "LITELLM_API_KEY is missing/empty. Add it to backend/.env even if another provider will be selected later."],
        ["ProfileNotFound for an empty profile", "Remove a blank AWS_PROFILE from the environment. The code handles the Docker empty-string case, but stale shell/container state may still need recreation."],
        ["Browser CORS or network error", "Make VITE_API_BASE_URL and CORS_ORIGINS match the actual scheme, host, and port; recreate containers after env changes."],
        ["Ollama unreachable from Docker", "Use a host-reachable address instead of container-local localhost and confirm the Ollama OpenAI-compatible /v1 endpoint."],
        ["Masking-service warnings", "The external service timed out, returned an error, or returned malformed data. Local masking continues; review connectivity/certificate/API key."],
        ["HTTP 429 before analysis", "Inbound client limit or provider quota. Slow requests, narrow the range, reduce chunks, or wait for quota."],
        ["HTTP 200 with warnings", "Some chunks succeeded and later quota/request failures occurred. Treat the text as partial and inspect chunks_analyzed/chunks_total."],
        ["No anomaly lines selected", "The default prefilter found no keywords and evenly sampled the slice. Ask a custom question to bypass that prefilter."],
        ["Chart counts differ from expectations", "Dashboard/facets use heuristics over only loaded and filtered events; check parsing patterns and pagination."],
    ],
    [3000, 5700],
)
heading("16.1 Known Design Constraints", 2)
bullet("No database: logs, chat, provider overrides, filters, and highlights disappear on reload.")
bullet("No application authentication: network exposure is the deployment owner's responsibility.")
bullet("Rate limiters are per process/worker. Multiple workers or replicas multiply the effective provider and inbound limits.")
bullet("The 7-day cap bounds requests but does not guarantee low AWS volume or low LLM cost. Narrow sources and filters whenever possible.")
bullet("CloudTrail LookupEvents is event history rather than an arbitrary long-term lake query. Retention/availability is governed by AWS CloudTrail behavior and account configuration.")
bullet("The dashboard and frontend facet parser are heuristic. LLM conclusions must still be verified against source systems and metrics.")
bullet("CloudWatch Logs Insights, durable saved investigations, frontend automated tests, authentication, production web serving, TLS termination, and distributed rate limiting are not implemented.")

heading("Appendix A. Data Models", 1)
heading("A.1 LogEvent", 2)
table(
    ["Field", "Type", "Description"],
    [
        ["source", "cloudwatch | cloudtrail", "Origin service"],
        ["origin", "string", "CloudWatch log-group name or cloudtrail"],
        ["stream_or_key", "string", "Log-stream name or CloudTrail event name"],
        ["timestamp", "datetime | null", "UTC-aware timestamp when available"],
        ["message", "string", "Masked log/event payload"],
        ["line_index", "integer", "Display/evidence index, stable for the loaded browser slice"],
    ],
    [2100, 2200, 4400],
)
heading("A.2 AnalysisRequest", 2)
table(
    ["Field", "Required", "Description"],
    [
        ["events", "Yes", "LogEvent array; max max_log_search_lines"],
        ["context.source_description", "Yes", "Human-readable source/time/filter description"],
        ["provider", "No", "litellm default; gemini, openai, anthropic, or ollama"],
        ["api_key / model / base_url", "No", "Provider overrides; blank values are normalized to null by the UI"],
        ["user_prompt", "No", "Custom log question; blank runs default anomaly scan"],
        ["history", "No", "Ordered user/assistant turns, max max_chat_history_messages"],
    ],
    [2600, 1500, 4600],
)

heading("Appendix B. Example Requests", 1)
heading("B.1 Health", 2)
code("curl http://localhost:8000/api/health")
heading("B.2 CloudWatch Search", 2)
code("curl -X POST http://localhost:8000/api/cloudwatch/logs/search \\\n  -H 'Content-Type: application/json' \\\n  -d '{\"log_group_names\":[\"/aws/lambda/example\"],\"start_time\":\"2026-08-18T00:00:00Z\",\"end_time\":\"2026-08-18T01:00:00Z\",\"filter_pattern\":\"ERROR\"}'")
heading("B.3 CloudTrail Search", 2)
code("curl -X POST http://localhost:8000/api/cloudtrail/events/search \\\n  -H 'Content-Type: application/json' \\\n  -d '{\"start_time\":\"2026-08-18T00:00:00Z\",\"end_time\":\"2026-08-18T01:00:00Z\",\"lookup_attribute_key\":\"EventName\",\"lookup_attribute_value\":\"ConsoleLogin\"}'")
heading("B.4 Provider Connection Test", 2)
code("curl -X POST http://localhost:8000/api/analysis/test-connection \\\n  -H 'Content-Type: application/json' \\\n  -d '{\"provider\":\"litellm\"}'")
heading("B.5 Local Mask Test", 2)
code("curl -X POST http://localhost:8000/api/mask/test \\\n  -H 'Content-Type: application/json' \\\n  -d '{\"lines\":[\"user@example.com from 192.0.2.5\"]}'")

paragraph("End of document", align="center", before=500, after=100)

# A4 section properties.
sect = el(body, "sectPr")
el(sect, "pgSz", attrs={"w": "11906", "h": "16838"})
el(sect, "pgMar", attrs={"top": "1134", "right": "1134", "bottom": "1134", "left": "1134", "header": "500", "footer": "500", "gutter": "0"})
el(sect, "cols", attrs={"space": "708"})
el(sect, "docGrid", attrs={"linePitch": "360"})


def update_settings(raw: bytes) -> bytes:
    root = ET.fromstring(raw)
    found = root.find(qn(W, "updateFields"))
    if found is None:
        found = ET.SubElement(root, qn(W, "updateFields"))
    found.set(qn(W, "val"), "true")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def update_core(raw: bytes) -> bytes:
    root = ET.fromstring(raw)
    values = {
        qn(DC, "title"): "CloudCortex Technical, Operations, API, and User Documentation",
        qn(DC, "subject"): "AWS log investigation and LLM-assisted APM",
        qn(DC, "creator"): "CloudCortex project",
        qn(CP, "keywords"): "CloudCortex, CloudWatch, CloudTrail, FastAPI, React, LLM, masking, APM",
        qn(CP, "lastModifiedBy"): "CloudCortex project",
    }
    for tag, value in values.items():
        node = root.find(tag)
        if node is None:
            node = ET.SubElement(root, tag)
        node.text = value
    modified = root.find(qn(DCT, "modified"))
    if modified is None:
        modified = ET.SubElement(root, qn(DCT, "modified"))
    modified.set(qn(XSI, "type"), "dcterms:W3CDTF")
    modified.text = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


if not DOCX.exists():
    raise SystemExit(f"Missing template: {DOCX}")

document_xml = ET.tostring(document, encoding="utf-8", xml_declaration=True)
with zipfile.ZipFile(DOCX, "r") as source, zipfile.ZipFile(TMP, "w", zipfile.ZIP_DEFLATED) as target:
    for info in source.infolist():
        if info.filename == "word/document.xml":
            target.writestr(info, document_xml)
        elif info.filename == "word/settings.xml":
            target.writestr(info, update_settings(source.read(info.filename)))
        elif info.filename == "docProps/core.xml":
            target.writestr(info, update_core(source.read(info.filename)))
        else:
            target.writestr(info, source.read(info.filename))

with zipfile.ZipFile(TMP, "r") as check:
    bad = check.testzip()
    if bad:
        raise SystemExit(f"Corrupt ZIP member: {bad}")
    ET.fromstring(check.read("word/document.xml"))
    required = {"[Content_Types].xml", "_rels/.rels", "word/document.xml", "word/styles.xml"}
    missing = required.difference(check.namelist())
    if missing:
        raise SystemExit(f"Missing DOCX members: {sorted(missing)}")

os.replace(TMP, DOCX)
print(f"Updated {DOCX.name}: {DOCX.stat().st_size} bytes")
