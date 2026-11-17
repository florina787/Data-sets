// MapLibre map, lazy-initialised. Falls back to the list when WebGL is unavailable.
import { useEffect, useRef, useState } from "react";
import type { Map as MLMap } from "maplibre-gl";
import { toGeoJSON, type Place } from "./places";

export function SisterhoodMap({ places, selected, onSelect, flyTo }: { places: Place[]; selected?: string; onSelect: (id: string) => void; flyTo?: { lat: number; lon: number; zoom?: number } | null }) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<MLMap | null>(null);
  const [state, setState] = useState<"loading" | "ready" | "unavailable">("loading");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const canvas = document.createElement("canvas");
        if (!(canvas.getContext("webgl2") || canvas.getContext("webgl"))) throw new Error("no webgl");
        const ml = await import("maplibre-gl");
        await import("maplibre-gl/dist/maplibre-gl.css");
        if (cancelled || !el.current) return;
        const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
        const m = new ml.Map({ container: el.current, style: "https://tiles.openfreemap.org/styles/liberty", center: [0, 25], zoom: 0.85, attributionControl: { compact: true }, cooperativeGestures: true, fadeDuration: reduce ? 0 : 300 });
        map.current = m;
        m.addControl(new ml.NavigationControl({ showCompass: false }), "top-right");
        m.on("load", () => {
          m.addSource("places", { type: "geojson", data: toGeoJSON(places), cluster: true, clusterRadius: 40, clusterMaxZoom: 6 });
          m.addLayer({ id: "clusters", type: "circle", source: "places", filter: ["has", "point_count"], paint: { "circle-color": "#17140f", "circle-radius": ["step", ["get", "point_count"], 16, 4, 22], "circle-stroke-width": 2, "circle-stroke-color": "#d7b57a" } });
          m.addLayer({ id: "cluster-count", type: "symbol", source: "places", filter: ["has", "point_count"], layout: { "text-field": ["get", "point_count_abbreviated"], "text-size": 13, "text-font": ["Noto Sans Bold"] }, paint: { "text-color": "#f7f1e6" } });
          m.addLayer({ id: "points", type: "circle", source: "places", filter: ["!", ["has", "point_count"]], paint: { "circle-color": "#a8844c", "circle-radius": 9, "circle-stroke-width": 3, "circle-stroke-color": "#fffdf9" } });
          m.on("click", "clusters", async (e) => {
            const f = m.queryRenderedFeatures(e.point, { layers: ["clusters"] })[0];
            const src = m.getSource("places") as unknown as { getClusterExpansionZoom: (id: number) => Promise<number> };
            const z = await src.getClusterExpansionZoom(f.properties.cluster_id);
            m.easeTo({ center: (f.geometry as unknown as { coordinates: [number, number] }).coordinates, zoom: z });
          });
          m.on("click", "points", (e) => { const id = e.features?.[0]?.properties?.id; if (id) onSelect(String(id)); });
          for (const l of ["clusters", "points"]) { m.on("mouseenter", l, () => (m.getCanvas().style.cursor = "pointer")); m.on("mouseleave", l, () => (m.getCanvas().style.cursor = "")); }
          setState("ready");
        });
        m.on("error", () => { /* tile hiccups shouldn't break the page */ });
      } catch { if (!cancelled) setState("unavailable"); }
    })();
    return () => { cancelled = true; map.current?.remove(); map.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const m = map.current; if (!m || state !== "ready") return;
    (m.getSource("places") as unknown as { setData: (d: unknown) => void } | undefined)?.setData(toGeoJSON(places));
  }, [places, state]);

  useEffect(() => {
    const m = map.current; if (!m || state !== "ready") return;
    const p = places.find((x) => x.id === selected);
    if (p?.lat !== undefined) m.flyTo({ center: [p.lon!, p.lat], zoom: p.scope === "city" ? 9 : 3.5, essential: false });
  }, [selected, state, places]);

  useEffect(() => { if (flyTo && map.current && state === "ready") map.current.flyTo({ center: [flyTo.lon, flyTo.lat], zoom: flyTo.zoom ?? 9 }); }, [flyTo, state]);

  return (
    <div className="relative h-[420px] overflow-hidden rounded-f bg-surface-2 md:h-[520px]">
      <div ref={el} className="h-full w-full" role="region" aria-label="World map of women's health organisations. The list beside it contains the same information." />
      {state === "loading" && <div className="absolute inset-0 grid place-items-center text-sm text-muted" role="status">Loading map…</div>}
      {state === "unavailable" && <div className="absolute inset-0 grid place-items-center p-6 text-center text-sm text-muted" role="status">The interactive map can't run on this device. Every organisation is in the list.</div>}
    </div>
  );
}
