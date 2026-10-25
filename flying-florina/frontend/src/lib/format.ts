export function fmt(v: unknown): string {
  if (v === null || v === undefined || v === "") return "-";
  if (typeof v === "boolean") return v ? "Yes" : "No";
  if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString() : v.toLocaleString(undefined, { maximumFractionDigits: 3 });
  if (Array.isArray(v)) return v.map(fmt).join(", ");
  if (typeof v === "object") return JSON.stringify(v);
  return String(v);
}

export function time(ts?: string | null): string {
  if (!ts) return "-";
  const d = new Date(ts);
  return isNaN(d.getTime()) ? ts : d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function datetime(ts?: string | null): string {
  if (!ts) return "-";
  const d = new Date(ts);
  return isNaN(d.getTime()) ? ts : d.toLocaleString();
}

/** Minimal, safe markdown: escapes HTML first, then applies bold, code and list formatting. */
export function miniMarkdown(src: string): string {
  const esc = src.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  const lines = esc.split("\n");
  const out: string[] = [];
  let inList = false;
  for (const line of lines) {
    const m = /^\s*[-*]\s+(.*)$/.exec(line);
    const inline = (t: string) => t.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>").replace(/`([^`]+)`/g, "<code>$1</code>");
    if (m) {
      if (!inList) out.push("<ul>");
      inList = true;
      out.push(`<li>${inline(m[1])}</li>`);
    } else {
      if (inList) out.push("</ul>");
      inList = false;
      if (line.trim()) out.push(`<p>${inline(line)}</p>`);
    }
  }
  if (inList) out.push("</ul>");
  return out.join("");
}
