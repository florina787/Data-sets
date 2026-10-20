// Chart tokens. Categorical order validated (dataviz validator) against the FLO card surface #162338 in dark mode:
// all checks pass, worst adjacent CVD dE 8.4. Gold is the brand accent and never a series colour; status colours are
// reserved for state. Scatter/map charts with all-pairs comparisons use at most the first three slots (others fold to "Other").
export const SERIES_DARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"];
export const SERIES_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];
export const STATUS = { good: "#10B981", warning: "#F59E0B", critical: "#EF4444" };
export const GOLD = "#D4AF37";

export function tokens() {
  const dark = document.documentElement.dataset.theme !== "light";
  return {
    dark,
    series: dark ? SERIES_DARK : SERIES_LIGHT,
    ink: dark ? "#ecf0f6" : "#0f172a",
    muted: dark ? "#94a3b8" : "#526075",
    grid: dark ? "rgba(148,163,184,0.12)" : "rgba(15,23,42,0.08)",
    surface: dark ? "#162338" : "#ffffff",
    // sequential: single blue hue light->dark (on dark surfaces higher magnitude = brighter)
    seq: dark ? ["#16304f", "#1f4f86", "#2f6fbf", "#4f91e6", "#93bdf2"] : ["#dbe9fb", "#a9cbf5", "#6aa3ec", "#2a78d6", "#174c8f"],
    // diverging: orange <- neutral gray -> blue
    div: dark ? ["#d95926", "#8a5a46", "#5b6576", "#3d6aa6", "#3987e5"] : ["#eb6834", "#f2b39a", "#c9ced6", "#8fb6ea", "#2a78d6"],
  };
}

export const baseOption = () => {
  const t = tokens();
  return {
    aria: { enabled: true, decal: { show: false } },
    color: t.series,
    textStyle: { color: t.muted, fontFamily: "Inter, system-ui, sans-serif" },
    grid: { left: 56, right: 18, top: 36, bottom: 32, containLabel: true },
    tooltip: { backgroundColor: t.surface, borderColor: t.grid, textStyle: { color: t.ink }, confine: true },
    legend: { textStyle: { color: t.muted }, top: 0, icon: "roundRect", itemWidth: 10, itemHeight: 10 },
  };
};

export const axis = (extra: object = {}) => {
  const t = tokens();
  return { axisLine: { lineStyle: { color: t.grid } }, axisLabel: { color: t.muted }, splitLine: { lineStyle: { color: t.grid } }, ...extra };
};
