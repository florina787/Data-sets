import { lazy, Suspense, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { BadgeCheck, ExternalLink, List, Map as MapIcon, Search, Users } from "lucide-react";
import { useApp } from "../../lib/app-state";
import { load } from "../../lib/storage";
import { Badge, Button, Card, Notice, PageHeader, inputCls } from "../../components/ui";
import type { Opportunity } from "../opportunities/data";
import { PLACES, PLACE_CATEGORIES, filterPlaces, geocode, type PlaceCategory } from "./places";

const SisterhoodMap = lazy(() => import("./SisterhoodMap").then((m) => ({ default: m.SisterhoodMap })));

const SCOPE_NOTE = { country: "Marker shows the country this organisation serves, not an address.", region: "Marker shows the region served, not an address.", city: "Marker shows the city served.", online: "Online: no map marker." };

export function SisterhoodPage() {
  const app = useApp();
  const [q, setQ] = useState("");
  const [cats, setCats] = useState<PlaceCategory[]>([]);
  const [freeOnly, setFreeOnly] = useState(false);
  const [view, setView] = useState<"map" | "list">("map");
  const [sel, setSel] = useState<string | undefined>();
  const [place, setPlace] = useState("");
  const [fly, setFly] = useState<{ lat: number; lon: number } | null>(null);
  const [geoMsg, setGeoMsg] = useState<string | null>(null);
  const list = useMemo(() => filterPlaces(PLACES, q, cats, freeOnly), [q, cats, freeOnly]);
  const selected = PLACES.find((p) => p.id === sel);
  const saved = load<Opportunity[]>(`saved-opps:${app.profile.id}`, []);

  async function findCity(e: React.FormEvent) {
    e.preventDefault(); if (!place.trim()) return;
    setGeoMsg("Searching OpenStreetMap…");
    try { const r = await geocode(place.trim()); if (r) { setFly(r); setView("map"); setGeoMsg(`Showing ${r.label.split(",").slice(0, 3).join(",")}`); } else setGeoMsg("No place found."); }
    catch { setGeoMsg("Search is unavailable offline."); }
  }

  return (
    <div>
      <PageHeader title="Global sisterhood" sub="Find menopause societies, women's health organisations, support communities and wellness directories around the world. Every listing is verified at its official website." />

      <div className="flex flex-wrap items-center gap-2">
        <label data-tour="sisterhood-search" className="relative min-w-56 flex-1"><span className="sr-only">Search organisations</span><Search size={15} className="absolute left-3 top-3 text-muted" />
          <input className={inputCls + " pl-9"} placeholder="Search by name, country, language or topic" value={q} onChange={(e) => setQ(e.target.value)} /></label>
        <form onSubmit={findCity} className="flex gap-2"><label><span className="sr-only">Go to a city or country on the map</span><input className={inputCls + " !w-52"} placeholder="Go to a city…" value={place} onChange={(e) => setPlace(e.target.value)} /></label><Button type="submit">Go</Button></form>
        <div className="flex rounded-full bg-surface-2 p-0.5" role="radiogroup" aria-label="View">
          <button role="radio" aria-checked={view === "map"} onClick={() => setView("map")} className={`flex items-center gap-1 rounded-full px-3 py-1.5 text-sm ${view === "map" ? "bg-surface shadow-f" : "text-muted"}`}><MapIcon size={14} /> Map</button>
          <button role="radio" aria-checked={view === "list"} onClick={() => setView("list")} className={`flex items-center gap-1 rounded-full px-3 py-1.5 text-sm ${view === "list" ? "bg-surface shadow-f" : "text-muted"}`}><List size={14} /> List</button>
        </div>
      </div>
      {geoMsg && <p className="mt-1 text-xs text-muted" role="status">{geoMsg} (only the text you typed is sent to OpenStreetMap's search)</p>}
      <div className="mt-3 flex flex-wrap gap-2">
        {PLACE_CATEGORIES.map((c) => { const on = cats.includes(c); return <button key={c} aria-pressed={on} onClick={() => setCats(on ? cats.filter((x) => x !== c) : [...cats, c])} className={`rounded-full px-3 py-1.5 text-sm ${on ? "bg-primary text-primary-ink" : "bg-surface shadow-f"}`}>{c}</button>; })}
        <label className="ml-auto flex items-center gap-2 text-sm"><input type="checkbox" checked={freeOnly} onChange={(e) => setFreeOnly(e.target.checked)} /> Free only</label>
      </div>

      <div className="mt-4 grid gap-5 lg:grid-cols-[1.6fr_1fr]">
        <div data-tour="sisterhood-map">
          {view === "map" ? <Suspense fallback={<div className="h-[420px] rounded-f bg-surface-2" />}><SisterhoodMap places={list} selected={sel} onSelect={setSel} flyTo={fly} /></Suspense> : (
            <ul className="grid gap-3 sm:grid-cols-2">{list.map((p) => (
              <li key={p.id}><button onClick={() => setSel(p.id)} aria-pressed={sel === p.id} className={`h-full w-full rounded-f bg-surface p-4 text-left shadow-f ${sel === p.id ? "ring-2 ring-accent" : ""}`}>
                <Badge tone="accent">{p.category}</Badge><div className="mt-1 font-display text-lg leading-snug">{p.name}</div><div className="text-sm text-muted">{p.area}</div></button></li>))}</ul>)}
          <p className="mt-2 text-xs text-muted">{list.length} of {PLACES.length} organisations · map tiles © OpenStreetMap contributors, OpenFreeMap</p>
        </div>

        <div className="space-y-5">
          {selected ? (
            <Card title={selected.name} actions={<Badge tone="good"><BadgeCheck size={12} /> Verified {selected.verifiedAt}</Badge>}>
              <div className="flex flex-wrap gap-1"><Badge tone="accent">{selected.category}</Badge><Badge>{selected.free === "free" ? "Free" : selected.free === "membership" ? "Membership" : "Free & paid"}</Badge></div>
              <p className="mt-2 text-sm">{selected.description}</p>
              <dl className="mt-3 grid grid-cols-2 gap-2 text-sm"><div><dt className="text-muted">Serves</dt><dd>{selected.area}</dd></div><div><dt className="text-muted">Languages</dt><dd>{selected.languages.join(", ")}</dd></div></dl>
              <p className="mt-2 text-xs text-muted">{SCOPE_NOTE[selected.scope]}</p>
              <a href={selected.url} target="_blank" rel="noreferrer"><Button variant="primary" className="mt-3"><ExternalLink size={16} /> Visit official website</Button></a>
            </Card>
          ) : (
            <Card title="Choose an organisation"><ul className="max-h-[440px] divide-y divide-line overflow-y-auto">{list.map((p) => (
              <li key={p.id}><button className="w-full py-2.5 text-left hover:text-primary" onClick={() => setSel(p.id)}><b className="font-medium">{p.name}</b><br /><span className="text-xs text-muted">{p.category} · {p.area}</span></button></li>))}
              {list.length === 0 && <li className="py-3 text-sm text-muted">No organisations match.</li>}</ul></Card>)}
          {selected && <Button variant="ghost" onClick={() => setSel(undefined)}>← All organisations</Button>}

          <Card title={<span className="flex items-center gap-2"><Users size={18} className="text-accent" /> Sisterhood circles</span>}>
            <p className="text-sm">Member circles (perimenopause, women living alone, food, fitness, career, book clubs and more) will open with secure accounts, moderation, reporting and blocking. Until then Muse won't pretend other members are here.</p>
            {saved.length > 0 && <p className="mt-2 text-sm">You've saved {saved.length} event{saved.length > 1 ? "s" : ""} in <Link className="text-primary underline" to="/app/free-care">Discover</Link>.</p>}
          </Card>
          <Notice tone="neutral">Your location is never shown to anyone. The map shows organisations only, and "Go to a city" only moves the map.</Notice>
        </div>
      </div>
    </div>
  );
}
