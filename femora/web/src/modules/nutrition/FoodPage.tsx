import { useEffect, useMemo, useState } from "react";
import { Camera, ChevronLeft, ChevronRight, Sparkles, Trash2 } from "lucide-react";
import { useApp } from "../../lib/app-state";
import { addDays, dayKey, uid } from "../../lib/storage";
import { Badge, Button, Card, Notice, PageHeader, Progress, inputCls } from "../../components/ui";
import { REGIONS, foodById, type Nutrient } from "./foods";
import { META, MEALS, parseNatural, searchFoods, sugarPct, totals, type LogEntry, type Meal } from "./engine";
import { EnergyDonut, SugarGauge, WeekChart, type DayPoint } from "./Charts";
import { FoodScanner } from "./FoodScanner";
import { loadLog, loadTargets, saveLog, saveTargets } from "./store";

const SHOWN: Nutrient[] = ["protein", "fiber", "calcium", "vitD", "iron", "b12", "addedSugar", "satFat", "sodium", "caffeine", "alcohol"];

const EVIDENCE: { topic: string; level: "Stronger evidence" | "Limited evidence" | "Unproven"; text: string }[] = [
  { topic: "Bone health", level: "Stronger evidence", text: "Adequate calcium and vitamin D, alongside weight-bearing exercise, support bone health after menopause." },
  { topic: "Muscle", level: "Stronger evidence", text: "Sufficient protein combined with strength training helps maintain muscle with age." },
  { topic: "Heart health", level: "Stronger evidence", text: "Diets rich in vegetables, legumes, whole grains and lower in saturated fat and sodium support cardiovascular health." },
  { topic: "Hot flashes", level: "Limited evidence", text: "Soy isoflavones show mixed results in trials. Some people notice alcohol, caffeine or spicy food as personal triggers." },
  { topic: "Sleep", level: "Limited evidence", text: "Reducing late caffeine and alcohol is commonly advised; individual effects vary." },
  { topic: "\"Menopause cure\" foods", level: "Unproven", text: "No food or supplement cures menopause. Be cautious of products that claim to." },
];

export function FoodPage() {
  const { profile, location } = useApp();
  const [scan, setScan] = useState(false);
  const [log, setLog] = useState<LogEntry[]>(() => loadLog(profile.id));
  const [targets, setTargets] = useState(() => loadTargets(profile.id));
  const [date, setDate] = useState(() => new Date());
  const [meal, setMeal] = useState<Meal>(() => { const h = new Date().getHours(); return h < 11 ? "Breakfast" : h < 15 ? "Lunch" : h < 20 ? "Dinner" : "Snacks"; });
  const [q, setQ] = useState("");
  const [region, setRegion] = useState(location?.region ?? "All");
  useEffect(() => { if (location) setRegion(location.region); }, [location]);
  const [nl, setNl] = useState("");
  const [nlNote, setNlNote] = useState<string | null>(null);

  useEffect(() => { setLog(loadLog(profile.id)); setTargets(loadTargets(profile.id)); }, [profile.id]);
  useEffect(() => saveLog(profile.id, log), [profile.id, log]);

  const dk = dayKey(date);
  const today = log.filter((e) => e.date === dk);
  const t = useMemo(() => totals(today), [today]);
  const results = searchFoods(q, region);
  const isToday = dk === dayKey(new Date());
  const week: DayPoint[] = useMemo(() => Array.from({ length: 7 }, (_, i) => {
    const d = addDays(date, i - 6); const v = totals(log.filter((e) => e.date === dayKey(d))).values;
    return { day: d.toLocaleDateString(undefined, { weekday: "short" }), protein: v.protein, calcium: v.calcium, fiber: v.fiber, sugarPct: sugarPct(v) };
  }), [log, date]);

  const add = (foodId: string, portion = 1, m: Meal = meal) => setLog((l) => [...l, { id: uid(), foodId, meal: m, portion, date: dk }]);

  function logNatural() {
    const r = parseNatural(nl);
    r.items.forEach((it) => add(it.food.id, it.portion, r.meal ?? meal));
    setNlNote(r.items.length
      ? `Added ${r.items.map((i) => `${i.food.name} ×${i.portion}`).join(", ")} to ${r.meal ?? meal}.` + (r.unmatched.length ? ` Couldn't find: ${r.unmatched.join(", ")}. Try the search below.` : "")
      : `I couldn't match that to the sample database. Try the search below.`);
    setNl("");
  }

  return (
    <div>
      <PageHeader title="Food & nutrition" status="demonstrated"
        sub={<>{location ? <>Eating in <b>{location.city}</b> ({location.region}). </> : null}Log meals from any cuisine in the world. Numbers are deterministic estimates from a curated sample database. Edit portions any time.</>}
        actions={<div className="flex items-center gap-2" aria-label="Choose day">
          <Button size="sm" aria-label="Previous day" onClick={() => setDate((d) => addDays(d, -1))}><ChevronLeft size={16} /></Button>
          <span className="min-w-36 text-center font-medium">{isToday ? "Today" : date.toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}</span>
          <Button size="sm" aria-label="Next day" disabled={isToday} onClick={() => setDate((d) => addDays(d, 1))}><ChevronRight size={16} /></Button>
        </div>} />

      <div className="grid gap-5 lg:grid-cols-[1.25fr_1fr]">
        <div className="space-y-5">
          <Card title={<span className="flex items-center gap-2"><Sparkles size={18} className="text-accent" /> Describe what you ate</span>}>
            <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (nl.trim()) logNatural(); }}>
              <label className="flex-1"><span className="sr-only">Describe your meal</span>
                <input className={inputCls} placeholder='e.g. "2 idli and sambar with chai for breakfast"' value={nl} onChange={(e) => setNl(e.target.value)} /></label>
              <Button type="submit" variant="primary" disabled={!nl.trim()}>Log</Button>
              <Button onClick={() => setScan(true)} aria-label="Scan food with camera"><Camera size={18} /> <span className="hidden sm:inline">Scan</span></Button>
            </form>
            {scan && <FoodScanner region={location?.region} onClose={() => setScan(false)} onAdd={(f) => add(f.id)} />}
            {nlNote && <p className="mt-2 text-sm text-muted" role="status">{nlNote}</p>}
            <p className="mt-2 text-xs text-muted">Natural-language logging uses a deterministic text matcher in this demo. The camera scanner captures a real photo; dish recognition is simulated.</p>
          </Card>

          <Card title="Meals">
            <div className="mb-3 flex flex-wrap gap-2" role="radiogroup" aria-label="Add to meal">
              {MEALS.map((m) => <button key={m} role="radio" aria-checked={meal === m} onClick={() => setMeal(m)} className={`rounded-full px-3 py-1.5 text-sm ${meal === m ? "bg-primary text-primary-ink" : "bg-surface-2"}`}>{m}</button>)}
            </div>
            {MEALS.map((m) => {
              const items = today.filter((e) => e.meal === m);
              const kcal = Math.round(totals(items).values.kcal);
              return (
                <div key={m} className="border-t border-line py-3 first:border-0">
                  <div className="mb-1 flex justify-between text-sm"><b>{m}</b><span className="text-muted">{kcal} kcal</span></div>
                  {items.length === 0 && <p className="text-sm text-muted">Nothing logged.</p>}
                  <ul className="space-y-1">
                    {items.map((e) => { const f = foodById(e.foodId)!; return (
                      <li key={e.id} className="flex items-center gap-3 text-sm">
                        <span className="text-xl" aria-hidden>{f.emoji}</span>
                        <span className="flex-1">{f.name} {f.plantEstrogen && <Badge tone="good">plant estrogens</Badge>}{(f.n.alcohol ?? 0) > 0 && <Badge tone="warn">alcohol</Badge>}{(f.n.caffeine ?? 0) >= 30 && <Badge tone="warn">caffeine</Badge>}<br /><span className="text-xs text-muted">{f.serving} per serving · {f.region} · sugar {sugarPct(f.n) ?? "–"}% of kcal</span></span>
                        <label className="flex items-center gap-1 text-xs text-muted">servings
                          <input type="number" min={0.25} step={0.25} value={e.portion} aria-label={`Servings of ${f.name}`} className={inputCls + " !w-20 !py-1"}
                            onChange={(ev) => { const v = Math.max(0.25, Number(ev.target.value) || 0.25); setLog((l) => l.map((x) => (x.id === e.id ? { ...x, portion: v } : x))); }} />
                        </label>
                        <button aria-label={`Remove ${f.name}`} className="rounded p-1 text-muted hover:text-danger" onClick={() => setLog((l) => l.filter((x) => x.id !== e.id))}><Trash2 size={15} /></button>
                      </li>); })}
                  </ul>
                </div>);
            })}
          </Card>

          <Card title="Add from the global food list">
            <div className="flex flex-wrap gap-2">
              <label className="min-w-48 flex-1"><span className="sr-only">Search foods</span><input className={inputCls} placeholder="Search dishes, ingredients or cuisines" value={q} onChange={(e) => setQ(e.target.value)} /></label>
              <label><span className="sr-only">Region</span><select className={inputCls} value={region} onChange={(e) => setRegion(e.target.value)}><option>All</option>{REGIONS.map((r) => <option key={r}>{r}</option>)}</select></label>
            </div>
            <ul className="mt-3 grid max-h-80 gap-2 overflow-y-auto sm:grid-cols-2">
              {results.map((f) => (
                <li key={f.id} className="flex items-center gap-3 rounded-f-sm bg-surface-2 p-2 text-sm">
                  <span className="text-xl" aria-hidden>{f.emoji}</span>
                  <span className="flex-1"><b className="font-medium">{f.name}</b><br /><span className="text-xs text-muted">{f.serving} · {f.n.kcal} kcal · {f.n.protein ?? "?"} g protein · sugar {sugarPct(f.n) ?? "–"}%</span></span>
                  <Button size="sm" variant="primary" aria-label={`Add ${f.name} to ${meal}`} onClick={() => add(f.id)}>+</Button>
                </li>))}
              {results.length === 0 && <li className="text-sm text-muted">No foods match. The demo database has {searchFoods("").length} dishes; production will use national food composition tables.</li>}
            </ul>
          </Card>
        </div>

        <div className="space-y-5">
          <Card title="Today at a glance">
            <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-1 xl:grid-cols-2">
              <div><h4 className="mb-2 text-sm font-medium">Where your energy came from</h4><EnergyDonut n={t.values} /></div>
              <div><h4 className="mb-2 text-sm font-medium">Sugar percentage</h4><SugarGauge n={t.values} label="Added sugar, share of today's calories" /></div>
            </div>
          </Card>
          <Card title="Your week"><WeekChart data={week} targets={{ protein: targets.protein ?? 60, calcium: targets.calcium ?? 1200, fiber: targets.fiber ?? 21 }} /></Card>
          <Card title="Today's nutrients" actions={<span className="text-sm text-muted">{Math.round(t.values.kcal)} kcal · {t.entries} items</span>}>
            <ul className="space-y-3">
              {SHOWN.map((k) => {
                const m = META[k]; const v = t.values[k]; const tg = targets[k];
                const over = m.kind === "limit" && tg !== undefined && v > tg;
                return (
                  <li key={k}>
                    <div className="flex justify-between text-sm"><span>{m.label} <span className="text-xs text-muted">{m.kind === "limit" ? "(limit)" : "(goal)"}</span></span>
                      <span className={over ? "font-medium text-warn" : ""}>{v} {m.unit}{tg !== undefined && <span className="text-muted"> / {tg}</span>}{t.missing[k] ? <span className="text-xs text-muted"> · no data for {t.missing[k]} item{t.missing[k]! > 1 ? "s" : ""}</span> : null}</span></div>
                    <Progress label={m.label} value={v} max={tg ?? 1} color={over ? "var(--f-warn)" : m.kind === "limit" ? "var(--f-muted)" : "var(--f-primary)"} />
                  </li>);
              })}
              <li className="text-sm">Plant-estrogen foods: <b>{t.plantEstrogenServings}</b> serving{t.plantEstrogenServings === 1 ? "" : "s"} <span className="text-xs text-muted">(soy, legumes, flax)</span></li>
            </ul>
            <Notice tone="neutral">Estimates only, from a sample database. Missing values are labelled, not counted as zero. This is not a measure of blood sugar or of any lab value.</Notice>
            <details className="mt-3 text-sm">
              <summary className="cursor-pointer font-medium text-primary">Edit my targets</summary>
              <div className="mt-2 grid grid-cols-2 gap-2">
                {SHOWN.map((k) => (
                  <label key={k} className="flex items-center justify-between gap-2">{META[k].label}
                    <input type="number" min={0} className={inputCls + " !w-24 !py-1"} value={targets[k] ?? ""} aria-label={`${META[k].label} target`}
                      onChange={(e) => { const nt = { ...targets, [k]: Number(e.target.value) }; setTargets(nt); saveTargets(profile.id, nt); }} /></label>))}
              </div>
              <p className="mt-2 text-xs text-muted">Defaults are general reference values for women over 50. Your clinician or dietitian may suggest different targets.</p>
            </details>
          </Card>

          <Card title="What the evidence says">
            <ul className="space-y-3">
              {EVIDENCE.map((e) => (
                <li key={e.topic} className="text-sm"><div className="flex items-center gap-2"><b>{e.topic}</b><Badge tone={e.level === "Stronger evidence" ? "good" : e.level === "Limited evidence" ? "warn" : "danger"}>{e.level}</Badge></div><p className="text-muted">{e.text}</p></li>))}
            </ul>
            <p className="mt-3 text-xs text-muted">Summaries pending the structured evidence review (docs/AUDIT.md §14). Not medical advice.</p>
          </Card>
        </div>
      </div>
    </div>
  );
}
