import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Search } from "lucide-react";
import { api, type SearchHit } from "../lib/api";
import { monogram } from "../lib/format";

export default function SymbolSearch() {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const inp = useRef<HTMLInputElement>(null);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); inp.current?.focus(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => {
    if (!q.trim()) { setHits([]); return; }
    const t = setTimeout(() => api.search(q.trim()).then((r) => setHits(r.results)).catch(() => setHits([])), 150);
    return () => clearTimeout(t);
  }, [q]);
  return (
    <div className="search" role="search">
      <Search size={16} aria-hidden="true" />
      <input ref={inp} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Symbol or sector"
        aria-label="Search symbol or sector" maxLength={20} />
      <span className="kbd">⌘</span><span className="kbd">K</span>
      {hits.length > 0 && (
        <div className="search-results">
          {hits.map((h) => (
            <Link key={h.ticker} to={`/stock/${h.ticker}`} onClick={() => setQ("")}>
              <span className="mono-badge" style={{ width: 28, height: 28, fontSize: 10 }}>{monogram(h.ticker)}</span>
              <span><b>{h.ticker}</b> <span className="muted">· {h.sector} · {h.exchange}</span></span>
              {h.delisted && <span className="faint" style={{ marginLeft: "auto" }}>delisted {String(h.delisted).slice(0, 10)}</span>}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
