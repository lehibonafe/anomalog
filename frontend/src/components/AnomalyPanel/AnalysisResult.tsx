import { Fragment } from "react";

import { useSelectionStore } from "../../state/selectionStore";

const LINE_REF = /\[(\d+)(?:-(\d+))?\]/g;

export function AnalysisResult({ text }: { text: string }) {
  const setHighlightedRange = useSelectionStore((s) => s.setHighlightedRange);

  const parts: React.ReactNode[] = [];
  let lastIndex = 0;
  let key = 0;
  LINE_REF.lastIndex = 0;

  for (const match of text.matchAll(LINE_REF)) {
    const index = match.index ?? 0;
    if (index > lastIndex) {
      parts.push(<Fragment key={key++}>{text.slice(lastIndex, index)}</Fragment>);
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
    parts.push(<Fragment key={key++}>{text.slice(lastIndex)}</Fragment>);
  }

  return <div className="analysis-result">{parts}</div>;
}
