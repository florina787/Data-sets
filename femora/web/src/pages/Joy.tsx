import { useState } from "react";
import { Trash2 } from "lucide-react";
import { useApp } from "../lib/app-state";
import { Button, Card, PageHeader, inputCls } from "../components/ui";

const CATS = ["Made me happy", "Felt confident", "Felt appreciated", "Activity I enjoyed", "People I love", "Music", "Places", "Hobbies", "Achievements", "Grateful for"];

export function Joy() {
  const { joy, addJoy, removeJoy } = useApp();
  const [cat, setCat] = useState(CATS[0]);
  const [text, setText] = useState("");
  const counts = CATS.map((c) => [c, joy.filter((j) => j.category === c).length] as const).filter(([, n]) => n > 0).sort((a, b) => b[1] - a[1]);
  return (
    <div>
      <PageHeader title="My Joy Map" status="demonstrated" sub="A private place for what lifts you. There's no pressure to be positive. Hard days belong in your journal too." />
      <div className="grid gap-5 lg:grid-cols-[1fr_1fr]">
        <Card title="Add a moment">
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); if (text.trim()) { addJoy(cat, text.trim()); setText(""); } }}>
            <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Category">
              {CATS.map((c) => <button type="button" key={c} role="radio" aria-checked={cat === c} onClick={() => setCat(c)} className={`rounded-full px-3 py-1.5 text-sm ${cat === c ? "bg-accent text-white" : "bg-surface-2"}`}>{c}</button>)}
            </div>
            <label className="block"><span className="sr-only">Describe the moment</span><textarea rows={3} className={inputCls} placeholder="What happened?" value={text} onChange={(e) => setText(e.target.value)} /></label>
            <Button type="submit" variant="primary" disabled={!text.trim()}>Save to my Joy Map</Button>
          </form>
        </Card>
        <Card title="Your patterns">
          {counts.length === 0 ? <p className="text-muted">As you add moments, you'll see what tends to bring you joy here, counted only from what you chose to record.</p> :
            <ul className="space-y-2">{counts.map(([c, n]) => <li key={c} className="flex items-center gap-3 text-sm"><span className="w-40">{c}</span><span className="h-3 rounded-full bg-accent" style={{ width: `${n * 24}px` }} /><span className="text-muted">{n}</span></li>)}</ul>}
        </Card>
      </div>
      <Card title="Moments" className="mt-5">
        {joy.length === 0 ? <p className="text-muted">Nothing yet.</p> : (
          <ul className="divide-y divide-line">{[...joy].reverse().map((j) => (
            <li key={j.id} className="flex items-center gap-3 py-2 text-sm"><span className="rounded-full bg-surface-2 px-2 py-0.5 text-xs">{j.category}</span><span className="flex-1">{j.text}</span><span className="text-xs text-muted">{new Date(j.at).toLocaleDateString()}</span>
              <button aria-label="Delete moment" className="text-muted hover:text-danger" onClick={() => removeJoy(j.id)}><Trash2 size={15} /></button></li>))}</ul>)}
      </Card>
    </div>
  );
}
