import { useEffect, useRef } from "react";

let plotlyPromise: Promise<any> | null = null;
function loadPlotly() {
  plotlyPromise ??= import("plotly.js-dist-min").then((m: any) => m.default ?? m);
  return plotlyPromise;
}

export const BASE_LAYOUT = {
  font: { family: "Inter, system-ui, sans-serif", size: 12, color: "#0F1F1A" },
  paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
  margin: { l: 64, r: 16, t: 40, b: 48 },
  xaxis: { gridcolor: "#EAF2EE", linecolor: "#DCE8E2", zeroline: false },
  yaxis: { gridcolor: "#EAF2EE", linecolor: "#DCE8E2", zeroline: true, zerolinecolor: "#C9D9D1" },
  legend: { orientation: "h", x: 0, y: 1.02, yanchor: "bottom", font: { size: 11 } },
  hoverlabel: { bgcolor: "#062A1F", bordercolor: "#062A1F", font: { color: "#fff", family: "Inter" } },
  hovermode: "x unified",
};

export interface PlotProps { data: any[]; layout?: any; height?: number; onClick?: (ev: any) => void; testId?: string; ariaLabel: string }

/** Interactive Plotly chart (lazy-loaded). Hover, zoom, legend toggling and click-through all work. */
export function Plot({ data, layout, height = 380, onClick, testId, ariaLabel }: PlotProps) {
  const ref = useRef<HTMLDivElement>(null);
  const clickRef = useRef(onClick);
  clickRef.current = onClick;
  useEffect(() => {
    let alive = true;
    const el = ref.current;
    if (!el || typeof window === "undefined" || (window as any).__NO_PLOTLY__) return;
    loadPlotly().then((Plotly) => {
      if (!alive || !el) return;
      const merged = { ...BASE_LAYOUT, ...layout, margin: { ...BASE_LAYOUT.margin, ...(layout?.margin ?? {}), t: Math.max(layout?.margin?.t ?? 40, layout?.showlegend === false ? 8 : 40) }, legend: { ...BASE_LAYOUT.legend, ...(layout?.legend ?? {}) }, xaxis: { ...BASE_LAYOUT.xaxis, ...(layout?.xaxis ?? {}) }, yaxis: { ...BASE_LAYOUT.yaxis, ...(layout?.yaxis ?? {}) }, height };
      Plotly.react(el, data, merged, { displaylogo: false, responsive: true, modeBarButtonsToRemove: ["lasso2d", "select2d"] });
      (el as any).removeAllListeners?.("plotly_click");
      (el as any).on?.("plotly_click", (ev: any) => clickRef.current?.(ev));
    }).catch(() => { /* chart library unavailable (tests) */ });
    return () => { alive = false; };
  }, [data, layout, height]);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(() => loadPlotly().then((P) => { try { P.Plots.resize(el); } catch { /* not yet plotted */ } }).catch(() => {}));
    ro.observe(el);
    return () => { ro.disconnect(); loadPlotly().then((P) => { try { P.purge(el); } catch { /* ignore */ } }).catch(() => {}); };
  }, []);
  return <div ref={ref} role="img" aria-label={ariaLabel} data-testid={testId ?? "plot"} style={{ width: "100%", minHeight: height }} />;
}
