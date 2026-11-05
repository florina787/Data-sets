import { useState } from "react";

// Visual stock shelf: each product on its warehouse shelf with one floating "key fact" tag.
// Drawn packs are generic illustrations (no brand artwork). All numbers come from the inventory API.

type Item = {
  sku: string; name: string; warehouse: string; on_hand: number; days_of_cover: number; lead_time_days: number;
  avg_daily_demand: number; reorder_point: number; status: string; inbound: { po: string; units: number; eta: string }[];
};

const LIQUID: Record<string, string> = {
  "FS-MANGO-355": "#f59e0b", "FS-ORANGE-355": "#fb923c", "FS-APPLE-355": "#a3e635", "FS-SPARKLIME-355": "#bef264",
  "BH-COLDBREW-300": "#7c4a2d", "NT-OATMILK-1L": "#efe3c8",
};
const TAG: Record<string, { bg: string; text: string; label: string }> = {
  critical: { bg: "#ef4444", text: "#fff", label: "Critical" },
  reorder: { bg: "#f59e0b", text: "#1a1203", label: "Reorder" },
  ok: { bg: "#10b981", text: "#03140d", label: "OK" },
};

function fact(i: Item): string {
  if (i.status === "critical") return `${i.days_of_cover} d left · lead ${i.lead_time_days} d`;
  if (i.status === "reorder") return `${i.days_of_cover} d left · reorder`;
  return `${i.days_of_cover} days of cover`;
}

function Pack({ sku, fill }: { sku: string; fill: number }) {
  const colour = LIQUID[sku] ?? "#38bdf8";
  const level = Math.max(0.08, Math.min(1, fill));
  if (sku.startsWith("NT-")) {  // carton
    return (
      <svg width="46" height="78" viewBox="0 0 46 78" aria-hidden>
        <path d="M6 18 L23 6 L40 18 V74 H6 Z" fill="#f5efe1" stroke="#cbbf9f" />
        <rect x="6" y={74 - 56 * level} width="34" height={56 * level} fill={colour} opacity="0.55" />
        <path d="M6 18 H40" stroke="#cbbf9f" />
        <rect x="11" y="34" width="24" height="14" rx="3" fill="#2563eb" opacity="0.85" />
      </svg>
    );
  }
  if (sku.startsWith("BH-")) {  // can
    return (
      <svg width="40" height="78" viewBox="0 0 40 78" aria-hidden>
        <rect x="5" y="10" width="30" height="64" rx="6" fill="#1f2937" stroke="#4b5563" />
        <rect x="7" y={72 - 58 * level} width="26" height={58 * level} rx="4" fill={colour} opacity="0.9" />
        <rect x="9" y="6" width="22" height="6" rx="2" fill="#9ca3af" />
        <rect x="9" y="34" width="22" height="12" rx="2" fill="#f8fafc" opacity="0.85" />
      </svg>
    );
  }
  return (  // bottle
    <svg width="40" height="78" viewBox="0 0 40 78" aria-hidden>
      <rect x="14" y="2" width="12" height="8" rx="2" fill="#e5e7eb" />
      <path d="M14 10 h12 v6 q10 4 10 14 v40 a4 4 0 0 1 -4 4 h-24 a4 4 0 0 1 -4 -4 v-40 q0 -10 10 -14 z" fill="rgba(255,255,255,0.12)" stroke="rgba(255,255,255,0.45)" />
      <clipPath id={`clip-${sku}`}><path d="M14 10 h12 v6 q10 4 10 14 v40 a4 4 0 0 1 -4 4 h-24 a4 4 0 0 1 -4 -4 v-40 q0 -10 10 -14 z" /></clipPath>
      <rect x="0" y={74 - 58 * level} width="40" height={58 * level} fill={colour} clipPath={`url(#clip-${sku})`} opacity="0.85" />
      <rect x="9" y="40" width="22" height="14" rx="2" fill="#f8fafc" opacity="0.9" />
    </svg>
  );
}

export function StockShelf({ items }: { items: Item[] }) {
  const [open, setOpen] = useState<string | null>(null);
  const warehouses = [...new Set(items.map((i) => i.warehouse))];
  return (
    <div className="space-y-6">
      {warehouses.map((wh) => (
        <div key={wh}>
          <div className="mb-1 flex items-center justify-between">
            <span className="label">{wh}</span>
            <span className="text-[11px] text-navy-600">Fill level = days of cover relative to twice the supplier lead time</span>
          </div>
          <div className="relative rounded-xl bg-gradient-to-b from-[#0b1d34] to-[#0e2440] px-3 pb-0 pt-16">
            <ul className="flex flex-wrap items-end justify-around gap-x-6 gap-y-16">
              {items.filter((i) => i.warehouse === wh).map((i) => {
                const tag = TAG[i.status] ?? TAG.ok;
                const key = `${i.warehouse}-${i.sku}`;
                return (
                  <li key={key} className="relative flex flex-col items-center">
                    <button onClick={() => setOpen(open === key ? null : key)} aria-expanded={open === key}
                      className="absolute -top-14 left-1/2 z-10 w-32 -translate-x-1/2 rounded-2xl px-2 py-1 text-center text-[11px] font-semibold leading-tight shadow-lg"
                      style={{ background: tag.bg, color: tag.text }} title={`${i.name} at ${i.warehouse}: ${fact(i)}`}
                      aria-label={`${i.name} at ${i.warehouse}: ${tag.label}, ${fact(i)}`}>
                      <span className="block uppercase tracking-wide">{tag.label}</span>
                      <span className="block font-medium">{fact(i)}</span>
                      <span className="absolute -bottom-1 left-1/2 h-2 w-2 -translate-x-1/2 rotate-45" style={{ background: tag.bg }} aria-hidden />
                    </button>
                    <Pack sku={i.sku} fill={i.days_of_cover / Math.max(1, 2 * i.lead_time_days)} />
                    <span className="mt-1 text-center text-[11px] text-navy-800">{i.name.replace(/^(FreshSip|Brewhouse|NutriTerra) /, "")}</span>
                    <span className="text-[10px] text-navy-600">{i.on_hand.toLocaleString()} on hand</span>
                    {open === key && (
                      <div className="absolute top-full z-20 mt-2 w-56 rounded-xl border border-surface-line bg-surface-raised p-3 text-xs shadow-card" role="dialog" aria-label={`${i.name} at ${i.warehouse}`}>
                        <div className="font-semibold text-navy-900">{i.name} · {i.warehouse}</div>
                        <div>On hand {i.on_hand.toLocaleString()} · demand {i.avg_daily_demand}/day</div>
                        <div>Cover {i.days_of_cover} d · lead time {i.lead_time_days} d</div>
                        <div>Reorder point {i.reorder_point.toLocaleString()}</div>
                        <div>Inbound: {i.inbound.map((x) => `${x.po} ${x.units.toLocaleString()} ETA ${x.eta}`).join(", ") || "none"}</div>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
            <div className="mt-2 h-3 rounded-b-xl bg-gradient-to-b from-[#233b58] to-[#152e4c] shadow-[0_6px_12px_-4px_rgba(0,0,0,0.6)]" aria-hidden />
          </div>
        </div>
      ))}
    </div>
  );
}
