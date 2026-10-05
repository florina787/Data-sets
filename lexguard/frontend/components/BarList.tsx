"use client";

import { num } from "@/lib/format";

/** Simple labelled horizontal bars (single series, one hue). */
export function BarList({ data, unit = "", max }: { data: { label: string; value: number }[]; unit?: string; max?: number }) {
  const m = max ?? Math.max(1, ...data.map((d) => d.value));
  return (
    <div className="stack" style={{ gap: 6 }}>
      {data.map((d) => (
        <div key={d.label}>
          <div className="row small" style={{ justifyContent: "space-between" }}><span>{d.label}</span><span className="mono">{num(d.value, d.value % 1 ? 1 : 0)}{unit}</span></div>
          <div className="bar"><span style={{ width: `${(d.value / m) * 100}%` }} /></div>
        </div>
      ))}
    </div>
  );
}
