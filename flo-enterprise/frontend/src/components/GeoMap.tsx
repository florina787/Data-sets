import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import { feature } from "topojson-client";
import world from "world-atlas/countries-110m.json";
import { compact, pct } from "@/lib/format";
import { tokens } from "@/lib/chartTheme";

// ISO-3166 numeric codes for the synthetic issuer countries (world-atlas uses numeric ids)
const NUM: Record<string, string> = { CA: "124", US: "840", GB: "826", DE: "276", FR: "250", CH: "756", NL: "528", JP: "392", AU: "036",
  KR: "410", CN: "156", IN: "356", BR: "076", MX: "484", TW: "158" };

export type GeoRow = { country: string; region: string; lat: number; lon: number; value: number; weight: number };

// Self-contained map: country polygons from world-atlas (bundled), no external tile server or API key.
export function GeoMap({ rows, height = 300, onSelect }: { rows: GeoRow[]; height?: number; onSelect?: (r: GeoRow) => void }) {
  const el = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!el.current) return;
    const tk = tokens();
    const byNum = Object.fromEntries(rows.map((r) => [NUM[r.country], r]));
    const fc = feature(world as any, (world as any).objects.countries) as any;
    fc.features.forEach((f: any) => {
      const r = byNum[f.id];
      f.properties = { ...f.properties, weight: r ? r.weight : 0, code: r?.country ?? "", value: r?.value ?? 0 };
    });
    const max = Math.max(...rows.map((r) => r.weight), 0.01);
    const map = new maplibregl.Map({
      container: el.current, attributionControl: false, center: [10, 30], zoom: 0.6, renderWorldCopies: false,
      style: { version: 8, sources: {}, layers: [{ id: "bg", type: "background", paint: { "background-color": tk.dark ? "#0e1a2c" : "#eef2f8" } }] },
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.on("load", () => {
      map.addSource("c", { type: "geojson", data: fc });
      map.addLayer({ id: "fill", type: "fill", source: "c", paint: {
        "fill-color": ["case", ["==", ["get", "weight"], 0], tk.dark ? "#1b2a42" : "#dfe5ee",
          ["interpolate", ["linear"], ["get", "weight"], 0, tk.seq[0], max * 0.25, tk.seq[1], max * 0.5, tk.seq[2], max * 0.75, tk.seq[3], max, tk.seq[4]]],
        "fill-opacity": 0.95 } });
      map.addLayer({ id: "line", type: "line", source: "c", paint: { "line-color": tk.surface, "line-width": 0.6 } });
      const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false });
      map.on("mousemove", "fill", (e) => {
        const p = e.features?.[0]?.properties as any;
        if (!p?.code) return popup.remove();
        map.getCanvas().style.cursor = "pointer";
        popup.setLngLat(e.lngLat).setHTML(`<div style="color:#0B1220;font:12px Inter"><b>${p.code}</b><br/>CAD ${compact(p.value)} · ${pct(p.weight)}</div>`).addTo(map);
      });
      map.on("mouseleave", "fill", () => { popup.remove(); map.getCanvas().style.cursor = ""; });
      map.on("click", "fill", (e) => {
        const code = (e.features?.[0]?.properties as any)?.code;
        const r = rows.find((x) => x.country === code);
        if (r && onSelect) onSelect(r);
      });
    });
    return () => map.remove();
  }, [rows, onSelect]);
  return <div ref={el} style={{ height }} className="rounded-md overflow-hidden" role="img" aria-label="Geographic exposure map; use the table view for exact values" />;
}
