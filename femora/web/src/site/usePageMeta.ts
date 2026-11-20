import { useEffect } from "react";

export const SITE_URL = (import.meta.env.VITE_SITE_URL as string | undefined) ?? "https://florina787.github.io/Bea/";

/** Unique title/description/canonical per page (static copies are also generated at build for crawlers). */
export function usePageMeta(title: string, description: string, path: string) {
  useEffect(() => {
    document.title = title;
    const set = (sel: string, attr: string, val: string) => { let el = document.head.querySelector(sel) as HTMLElement | null; if (!el) { el = document.createElement(sel.startsWith("link") ? "link" : "meta"); const m = sel.match(/\[(\w+(?::\w+)?)="([^"]+)"\]/); if (m) el.setAttribute(m[1], m[2]); document.head.appendChild(el); } el.setAttribute(attr, val); };
    const url = SITE_URL.replace(/\/$/, "") + path;
    set('meta[name="description"]', "content", description);
    set('link[rel="canonical"]', "href", url);
    set('meta[property="og:title"]', "content", title);
    set('meta[property="og:description"]', "content", description);
    set('meta[property="og:url"]', "content", url);
  }, [title, description, path]);
}
