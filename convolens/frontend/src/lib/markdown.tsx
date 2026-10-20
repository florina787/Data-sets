// Minimal, XSS-safe Markdown renderer: every piece of text becomes a React text node (no HTML injection).
// Supports paragraphs, **bold**, "- " lists, "> " quotes and citation tokens [E1] / [M2].
import type { ReactNode } from "react";

type Props = { text: string; onCite?: (ref: string) => void };

function inline(s: string, onCite?: (ref: string) => void, keyBase = ""): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /(\*\*[^*]+\*\*|\[(?:E|M)\d+\])/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  while ((m = re.exec(s))) {
    if (m.index > last) out.push(s.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) out.push(<strong key={`${keyBase}b${i}`} className="font-semibold">{tok.slice(2, -2)}</strong>);
    else {
      const ref = tok.slice(1, -1);
      out.push(onCite ? (
        <button key={`${keyBase}c${i}`} type="button" onClick={() => onCite(ref)} className="mx-0.5 rounded bg-teal-light px-1 text-[11px] font-semibold text-teal hover:underline" aria-label={`Open ${ref.startsWith("E") ? "evidence" : "metric"} ${ref}`}>{ref}</button>
      ) : <span key={`${keyBase}c${i}`} className="text-[11px] font-semibold text-teal">{tok}</span>);
    }
    last = m.index + tok.length;
    i++;
  }
  if (last < s.length) out.push(s.slice(last));
  return out;
}

export function Markdown({ text, onCite }: Props) {
  const blocks: ReactNode[] = [];
  const lines = (text || "").split("\n");
  let list: string[] = [];
  const flush = (k: number) => {
    if (list.length) {
      blocks.push(<ul key={`l${k}`} className="my-1 list-disc space-y-0.5 pl-5">{list.map((l, i) => <li key={i}>{inline(l, onCite, `l${k}${i}`)}</li>)}</ul>);
      list = [];
    }
  };
  lines.forEach((raw, k) => {
    const line = raw.trimEnd();
    if (/^\s*[-*]\s+/.test(line)) { list.push(line.replace(/^\s*[-*]\s+/, "")); return; }
    flush(k);
    if (!line.trim()) return;
    if (line.startsWith(">")) blocks.push(<blockquote key={k} className="my-1 border-l-2 border-amber pl-2 text-[13px] text-[#7a4805]">{inline(line.replace(/^>\s?/, ""), onCite, `q${k}`)}</blockquote>);
    else if (/^#{1,4}\s/.test(line)) blocks.push(<p key={k} className="mt-2 font-semibold">{inline(line.replace(/^#+\s/, ""), onCite, `h${k}`)}</p>);
    else if (/^\*\*[^*]+\*\*$/.test(line.trim())) blocks.push(<p key={k} className="mt-2.5 text-[12px] font-semibold uppercase tracking-wide text-muted">{line.trim().slice(2, -2)}</p>);
    else blocks.push(<p key={k} className="my-1">{inline(line, onCite, `p${k}`)}</p>);
  });
  flush(lines.length);
  return <div className="text-sm leading-relaxed text-ink">{blocks}</div>;
}
