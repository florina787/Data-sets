import { useMemo, useState } from "react";
import { fmt } from "@/lib/format";
import { Badge, statusTone } from "./ui";

export type Column = { key: string; label: string; render?: (row: Record<string, unknown>) => React.ReactNode };

const BADGE_KEYS = new Set(["status", "decision", "severity", "compliant", "ok", "passed", "approved", "verified", "conflict", "pin_ok", "classification"]);

function cell(key: string, v: unknown) {
  if (BADGE_KEYS.has(key)) {
    if (typeof v === "boolean") {
      const good = key === "conflict" ? !v : v;
      return <Badge tone={good ? "teal" : key === "conflict" ? "amber" : "red"}>{v ? "Yes" : "No"}</Badge>;
    }
    if (typeof v === "string") {
      const tone = key === "severity" ? (v === "high" ? "red" : v === "medium" ? "amber" : "gray") : key === "classification" ? (v === "RESTRICTED" ? "red" : v === "UNKNOWN" ? "amber" : "purple") : statusTone(v);
      return <Badge tone={tone}>{v}</Badge>;
    }
  }
  return fmt(v);
}

export function DataTable({ columns, rows, maxHeight = 360, pageSize = 50, label }: { columns: Column[]; rows: Record<string, unknown>[]; maxHeight?: number; pageSize?: number; label?: string }) {
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 } | null>(null);
  const [page, setPage] = useState(0);
  const sorted = useMemo(() => {
    if (!sort) return rows;
    return [...rows].sort((a, b) => {
      const x = a[sort.key] as never;
      const y = b[sort.key] as never;
      return (x > y ? 1 : x < y ? -1 : 0) * sort.dir;
    });
  }, [rows, sort]);
  const pages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const view = sorted.slice(page * pageSize, (page + 1) * pageSize);
  if (!rows.length) return <div className="muted p-3 text-xs">No rows.</div>;
  return (
    <div>
      <div className="overflow-auto rounded-lg border border-token" style={{ maxHeight }}>
        <table className="ff" aria-label={label}>
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c.key} scope="col">
                  <button className="font-semibold" onClick={() => setSort((s) => ({ key: c.key, dir: s?.key === c.key && s.dir === 1 ? -1 : 1 }))} aria-label={`Sort by ${c.label}`}>
                    {c.label}
                    {sort?.key === c.key ? (sort.dir === 1 ? " ▲" : " ▼") : ""}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {view.map((r, i) => (
              <tr key={i}>
                {columns.map((c) => (
                  <td key={c.key}>{c.render ? c.render(r) : cell(c.key, r[c.key])}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {pages > 1 && (
        <div className="muted mt-2 flex items-center gap-2 text-xs">
          <button className="btn btn-ghost !py-1" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>
            Prev
          </button>
          Page {page + 1} / {pages} ({rows.length} rows)
          <button className="btn btn-ghost !py-1" disabled={page >= pages - 1} onClick={() => setPage((p) => p + 1)}>
            Next
          </button>
        </div>
      )}
    </div>
  );
}
