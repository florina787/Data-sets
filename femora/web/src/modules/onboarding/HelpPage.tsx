import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { MessageCircleHeart, PlayCircle, RotateCcw, Search } from "lucide-react";
import { Button, Card, PageHeader, inputCls } from "../../components/ui";
import { save } from "../../lib/storage";
import { ARTICLES, searchHelp } from "./help";
import { TOURS, tourStore } from "./tours";

export function HelpPage() {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const nav = useNavigate();
  const list = useMemo(() => searchHelp(q), [q]);
  const base = import.meta.env.BASE_URL;
  return (
    <div>
      <PageHeader title="Help centre" sub="Quick answers, short how-to animations and guided tours of every part of Muse." />
      <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
        <div>
          <label className="relative block"><span className="sr-only">Search help</span><Search size={16} className="absolute left-3 top-3.5 text-muted" />
            <input data-tour="help-search" className={inputCls + " pl-9 !py-3"} placeholder="Search, e.g. 'medication reminder' or 'delete my data'" value={q} onChange={(e) => setQ(e.target.value)} /></label>
          <ul className="mt-4 space-y-3">{list.map((a) => (
            <li key={a.id} className="rounded-f bg-surface shadow-f">
              <button className="w-full px-5 py-4 text-left font-display text-lg" aria-expanded={open === a.id} onClick={() => setOpen(open === a.id ? null : a.id)}>{a.title}</button>
              {open === a.id && <div className="f-enter px-5 pb-5">
                <ol className="list-decimal space-y-1 pl-5 text-sm">{a.steps.map((s) => <li key={s}>{s}</li>)}</ol>
                {a.video && <video className="mt-3 w-full rounded-f-sm ring-1 ring-line" src={`${base}help/${a.video}.webm`} poster={`${base}help/${a.video}.jpg`} controls muted loop playsInline preload="none" aria-label={`Short animation: ${a.title}`} />}
                {a.tour && <Button className="mt-3" variant="primary" onClick={() => tourStore.start(a.tour!)}><PlayCircle size={16} /> Show me</Button>}
              </div>}
            </li>))}
            {list.length === 0 && <li className="text-sm text-muted">No answers match. Try asking Muse.</li>}</ul>
        </div>
        <div className="space-y-5">
          <Card title="Guided tours"><ul className="space-y-2">{TOURS.map((t) => <li key={t.id}><button className="flex w-full items-center gap-2 rounded-f-sm px-2 py-2 text-left hover:bg-surface-2" onClick={() => tourStore.start(t.id)}><PlayCircle size={16} className="text-accent" /> {t.title} <span className="ml-auto text-xs text-muted">{t.steps.length} steps</span></button></li>)}</ul></Card>
          <Card title="Ask Muse how to">
            <p className="text-sm text-muted">Ask in your own words, like "how do I export my health records?". Muse answers from this help centre.</p>
            <Button className="mt-3" onClick={() => nav("/app/copilot")}><MessageCircleHeart size={16} /> Ask Muse</Button>
          </Card>
          <Card title="Start again">
            <p className="text-sm text-muted">Replay the welcome experience. Your data isn't changed.</p>
            <Button className="mt-3" onClick={() => { save("onboarded", false); location.reload(); }}><RotateCcw size={16} /> Restart welcome</Button>
          </Card>
          <p className="text-xs text-muted">{ARTICLES.length} articles · animations recorded from the real app.</p>
        </div>
      </div>
    </div>
  );
}
