import { useEffect, useState } from "react";

export type Route = { page: string; caseId?: string };

export function parseHash(hash: string): Route {
  const parts = hash.replace(/^#\/?/, "").split("/").filter(Boolean);
  return { page: parts[0] || "overview", caseId: parts[1] ? decodeURIComponent(parts[1]) : undefined };
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parseHash(window.location.hash));
  useEffect(() => {
    const on = () => setRoute(parseHash(window.location.hash));
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return route;
}

export function go(page: string, caseId?: string) {
  window.location.hash = caseId ? `#/${page}/${encodeURIComponent(caseId)}` : `#/${page}`;
}
