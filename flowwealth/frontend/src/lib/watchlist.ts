const KEY = "fw.watchlist";
export const getWatchlist = (): string[] => {
  try { const v = JSON.parse(localStorage.getItem(KEY) ?? "[]"); return Array.isArray(v) ? v.filter((x) => typeof x === "string") : []; }
  catch { return []; }
};
export const setWatchlist = (v: string[]) => localStorage.setItem(KEY, JSON.stringify([...new Set(v)].slice(0, 50)));
export const toggleWatch = (t: string) => {
  const w = getWatchlist();
  setWatchlist(w.includes(t) ? w.filter((x) => x !== t) : [...w, t]);
  return getWatchlist();
};
