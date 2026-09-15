import { Fragment, type ReactNode } from "react";

import { useSelectionStore } from "../../state/selectionStore";

// Accept individual lines, ranges, and comma-separated references emitted by
// different models: [399], [399-401], and [399, 401].
const LINE_REF = /\[\s*(\d+(?:\s*[-–—]\s*\d+)?(?:\s*,\s*\d+(?:\s*[-–—]\s*\d+)?)*)\s*\]/g;
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

  function showEvidence(ranges: Array<{ start: number; end: number }>) {
    const start = Math.min(...ranges.map((range) => range.start));
    const end = Math.max(...ranges.map((range) => range.end));
    setHighlightedRange({ start, end, ranges });
    window.requestAnimationFrame(() => {
      document.querySelector<HTMLElement>('.raw-logs-section')?.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
      });
    });
  }

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
    const references = match[1].split(',').map((reference) => {
      const bounds = [...reference.matchAll(/\d+/g)].map((value) => Number(value[0]));
      const first = bounds[0];
      const last = bounds[bounds.length - 1] ?? first;
      return {
        label: reference.trim(),
        range: { start: Math.min(first, last), end: Math.max(first, last) },
      };
    });
    parts.push(
      <span key={key++} className="line-ref-group">
        [
        {references.map(({ label, range }, referenceIndex) => (
          <Fragment key={`${label}-${referenceIndex}`}>
            {referenceIndex > 0 && ', '}
            <button
              type="button"
              className="line-ref"
              aria-label={range.start === range.end
                ? `Show referenced log ${range.start}`
                : `Show referenced logs ${range.start} through ${range.end}`}
              onClick={() => showEvidence([range])}
            >
              {label}
            </button>
          </Fragment>
        ))}
        ]
      </span>
    );
    lastIndex = index + match[0].length;
  }
  if (lastIndex < text.length) {
    const segKey = key++;
    parts.push(<Fragment key={segKey}>{renderInline(text.slice(lastIndex), `seg-${segKey}`)}</Fragment>);
  }

  return <div className={className ?? "analysis-result"}>{parts}</div>;
}
