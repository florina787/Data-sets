import type { JSX } from "react";
import { inlineSegments } from "../lib/format";

/** Renders FloPilot's minimal markdown as React elements (never as raw HTML). */
export function RichText({ text }: { text: string }) {
  const blocks: JSX.Element[] = [];
  let list: string[] = [];
  const flush = (key: string) => {
    if (list.length) {
      blocks.push(<ul key={key}>{list.map((item, i) => <li key={i}><Inline text={item} /></li>)}</ul>);
      list = [];
    }
  };
  text.split("\n").forEach((line, i) => {
    if (/^\s*- /.test(line)) {
      list.push(line.replace(/^\s*- /, ""));
      return;
    }
    flush(`l${i}`);
    if (line.trim()) blocks.push(<p key={i}><Inline text={line} /></p>);
  });
  flush("end");
  return <>{blocks}</>;
}

function Inline({ text }: { text: string }) {
  const italic = /^_(.+)_$/.exec(text.trim());
  if (italic) return <em>{italic[1]}</em>;
  return (
    <>
      {inlineSegments(text).map((s, i) =>
        s.kind === "bold" ? <strong key={i}>{s.text}</strong> : s.kind === "code" ? <code key={i}>{s.text}</code> : <span key={i}>{s.text}</span>,
      )}
    </>
  );
}
