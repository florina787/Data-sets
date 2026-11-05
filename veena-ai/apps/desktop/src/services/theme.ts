// Night (default) or day theme. Stored per device; falls back to night when
// storage is unavailable.
export type Theme = "night" | "day";

const KEY = "veena.theme";

export function getTheme(): Theme {
  try {
    return localStorage.getItem(KEY) === "day" ? "day" : "night";
  } catch {
    return "night";
  }
}

export function applyTheme(theme: Theme) {
  document.documentElement.classList.toggle("night", theme === "night");
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    /* storage blocked: the theme still applies for this session */
  }
}
