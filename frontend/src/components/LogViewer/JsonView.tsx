const INDENT_PX = 14;

function JsonPrimitive({ value }: { value: unknown }) {
  if (value === null) return <span className="json-null">null</span>;
  if (typeof value === "string") return <span className="json-string">"{value}"</span>;
  if (typeof value === "number") return <span className="json-number">{value}</span>;
  if (typeof value === "boolean") return <span className="json-boolean">{String(value)}</span>;
  return null;
}

function JsonNode({ value, depth }: { value: unknown; depth: number }) {
  if (Array.isArray(value)) {
    if (value.length === 0) return <span className="json-punct">[]</span>;
    return (
      <>
        <span className="json-punct">[</span>
        {value.map((item, i) => (
          <div key={i} className="json-line" style={{ paddingLeft: (depth + 1) * INDENT_PX }}>
            <JsonNode value={item} depth={depth + 1} />
            {i < value.length - 1 && <span className="json-punct">,</span>}
          </div>
        ))}
        <div className="json-line" style={{ paddingLeft: depth * INDENT_PX }}>
          <span className="json-punct">]</span>
        </div>
      </>
    );
  }

  if (value !== null && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) return <span className="json-punct">{"{}"}</span>;
    return (
      <>
        <span className="json-punct">{"{"}</span>
        {entries.map(([key, val], i) => (
          <div key={key} className="json-line" style={{ paddingLeft: (depth + 1) * INDENT_PX }}>
            <span className="json-key">"{key}"</span>
            <span className="json-punct">: </span>
            <JsonNode value={val} depth={depth + 1} />
            {i < entries.length - 1 && <span className="json-punct">,</span>}
          </div>
        ))}
        <div className="json-line" style={{ paddingLeft: depth * INDENT_PX }}>
          <span className="json-punct">{"}"}</span>
        </div>
      </>
    );
  }

  return <JsonPrimitive value={value} />;
}

export function JsonBlock({ value }: { value: unknown }) {
  return (
    <div className="json-view">
      <div className="json-line">
        <JsonNode value={value} depth={0} />
      </div>
    </div>
  );
}
