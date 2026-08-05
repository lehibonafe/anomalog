import { Fragment, type ReactNode } from "react";

import { useSelectionStore } from "../../state/selectionStore";

const LINE_REF = /\[(\d+)(?:-(\d+))?\]/g;
// Bold must be tried before italic so `**x**` isn't consumed as `*` + `*x*` + `*`.
const INLINE_MD = /\*\*(?<bold>[^*]+?)\*\*|`(?<code>[^`]+?)`|\*(?<italic>[^*]+?)\*/g;

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let lastIndex = 0;
  let key = 0;

  for (const match of text.matchAll(INLINE_MD)) {
    const index = match.index ?? 0;
    if (index > lastIndex) nodes.push(text.slice(lastIndex, index));
    const groups = match.groups ?? {};
    if (groups.bold !== undefined) {
      nodes.push(<strong key={`${keyPrefix}-${key++}`}>{groups.bold}</strong>);
    } else if (groups.code !== undefined) {
      nodes.push(
        <code key={`${keyPrefix}-${key++}`} className="analysis-code">
          {groups.code}
        </code>
      );
    } else if (groups.italic !== undefined) {
      nodes.push(<em key={`${keyPrefix}-${key++}`}>{groups.italic}</em>);
    }
    lastIndex = index + match[0].length;
  }
  if (lastIndex < text.length) nodes.push(text.slice(lastIndex));
  return nodes;
}

export function AnalysisResult({ text, className }: { text: string; className?: string }) {
  const setHighlightedRange = useSelectionStore((s) => s.setHighlightedRange);

  const parts: ReactNode[] = [];
  let lastIndex = 0;
  let key = 0;
  LINE_REF.lastIndex = 0;

  for (const match of text.matchAll(LINE_REF)) {
    const index = match.index ?? 0;
    if (index > lastIndex) {
      const segKey = key++;
      parts.push(<Fragment key={segKey}>{renderInline(text.slice(lastIndex, index), `seg-${segKey}`)}</Fragment>);
    }
    const start = Number(match[1]);
    const end = match[2] ? Number(match[2]) : start;
    parts.push(
      <button
        key={key++}
        type="button"
        className="line-ref"
        onClick={() => setHighlightedRange({ start, end })}
      >
        {match[0]}
      </button>
    );
    lastIndex = index + match[0].length;
  }
  if (lastIndex < text.length) {
    const segKey = key++;
    parts.push(<Fragment key={segKey}>{renderInline(text.slice(lastIndex), `seg-${segKey}`)}</Fragment>);
  }

  return <div className={className ?? "analysis-result"}>{parts}</div>;
}
