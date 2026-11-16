// Reused from ConvoLens (convolens/frontend/src/lib/markdown.tsx): XSS-safe Markdown, every piece of text becomes a
// React text node. Adapted: citation tokens are [S1]-style source references.
import type { ReactNode } from "react";

function inline(s: string, onCite?: (ref: string) => void, keyBase = ""): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|\[S\d+\])/g;
  let last = 0, i = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(s))) {
    if (m.index > last) out.push(s.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) out.push(<strong key={`${keyBase}b${i}`} className="font-semibold">{tok.slice(2, -2)}</strong>);
    else {
      const ref = tok.slice(1, -1);
      out.push(onCite
        ? <button key={`${keyBase}c${i}`} type="button" onClick={() => onCite(ref)} aria-label={`Open source ${ref}`} className="mx-0.5 rounded bg-surface-2 px-1 text-[11px] font-semibold text-primary hover:underline">{ref}</button>
        : <span key={`${keyBase}c${i}`} className="mx-0.5 text-[11px] font-semibold text-primary">[{ref}]</span>);
    }
    last = m.index + tok.length;
    i++;
  }
  if (last < s.length) out.push(s.slice(last));
  return out;
}

export function Markdown({ text, onCite }: { text: string; onCite?: (ref: string) => void }) {
  const blocks: ReactNode[] = [];
  let list: string[] = [];
  const flush = (k: number) => {
    if (list.length) {
      blocks.push(<ul key={`l${k}`} className="my-1 list-disc space-y-0.5 pl-5">{list.map((l, i) => <li key={i}>{inline(l, onCite, `l${k}${i}`)}</li>)}</ul>);
      list = [];
    }
  };
  const lines = (text || "").split("\n");
  lines.forEach((raw, k) => {
    const line = raw.trimEnd();
    if (/^\s*[-*]\s+/.test(line)) { list.push(line.replace(/^\s*[-*]\s+/, "")); return; }
    flush(k);
    if (!line.trim()) return;
    if (line.startsWith(">")) blocks.push(<blockquote key={k} className="my-1 border-l-2 border-accent pl-2 text-[13px] text-muted">{inline(line.replace(/^>\s?/, ""), onCite, `q${k}`)}</blockquote>);
    else blocks.push(<p key={k} className="my-1">{inline(line, onCite, `p${k}`)}</p>);
  });
  flush(lines.length);
  return <div className="text-[15px] leading-relaxed">{blocks}</div>;
}
