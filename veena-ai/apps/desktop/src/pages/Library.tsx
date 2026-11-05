import { ArrowLeft, BookOpen, BriefcaseBusiness, MessagesSquare, Monitor, Plus, Search, Trash2, Users } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { TopBar } from "../components/Shell";
import { Badge, Button, Card, cn, Input, Select } from "../components/ui";
import type { Session } from "../services/api";
import { type Page, useApp } from "../stores/app";

type Mode = Session["mode"];

const FOLDERS: { mode: Mode; title: string; unit: string; icon: typeof MessagesSquare; page: Page }[] = [
  { mode: "conversation", title: "Conversations", unit: "conversations", icon: MessagesSquare, page: "workspace" },
  { mode: "meeting", title: "Meetings", unit: "meetings", icon: Users, page: "meeting" },
  { mode: "screen", title: "Screen sessions", unit: "sessions", icon: Monitor, page: "screen" },
  { mode: "interview", title: "Interview practice", unit: "practices", icon: BriefcaseBusiness, page: "interview" },
];

function parse(iso: string) {
  return new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
}

/** A folder with the newest sessions peeking out of it, like paper in a file folder. */
function FolderCard({ title, count, unit, peek, onOpen, icon: Icon }: { title: string; count: number; unit: string; peek: string[]; onOpen: () => void; icon: typeof MessagesSquare }) {
  const empty = count === 0;
  return (
    <button type="button" onClick={onOpen} className="group flex flex-col items-center text-center" aria-label={`Open ${title}`}>
      <div className="relative h-44 w-56">
        {!empty &&
          peek.slice(0, 3).map((t, i) => (
            <div
              key={t + i}
              className="absolute top-0 left-1/2 h-24 w-36 rounded-xl border border-cream bg-white p-2 text-left text-[10px] leading-snug text-mocha shadow-[var(--shadow-soft)] transition-transform group-hover:-translate-y-2"
              style={{ transform: `translateX(-50%) translateX(${(i - 1) * 34}px) rotate(${(i - 1) * 8}deg)` }}
            >
              <span className="line-clamp-4">{t}</span>
            </div>
          ))}
        {/* folder back tab */}
        <div className={cn("absolute top-14 left-5 h-6 w-20 rounded-t-xl", empty ? "bg-cream" : "bg-caramel")} />
        {/* folder front */}
        <div
          className={cn(
            "absolute inset-x-0 bottom-0 flex h-28 items-end justify-center rounded-2xl pb-3 shadow-[var(--shadow-lift)]",
            empty ? "border border-dashed border-sand bg-white" : "bg-gradient-to-b from-ginger to-caramel",
          )}
        >
          <Icon size={22} className={empty ? "text-sand" : "text-white"} />
        </div>
      </div>
      <p className="mt-3 text-sm font-semibold text-espresso">{title}</p>
      <Badge className="mt-1">
        {count} {count === 1 ? unit.replace(/s$/, "") : unit}
      </Badge>
    </button>
  );
}

function NotesGrid({ mode, onBack }: { mode: Mode; onBack: () => void }) {
  const { api, newSession, openSession, deleteSession, setPage } = useApp();
  const folder = FOLDERS.find((f) => f.mode === mode)!;
  const [items, setItems] = useState<Session[]>([]);
  const [q, setQ] = useState("");
  const [range, setRange] = useState("all");

  const load = async () => {
    if (!api) return;
    const qs = new URLSearchParams({ mode });
    if (q) qs.set("q", q);
    setItems(await api.get<Session[]>(`/api/sessions?${qs}`));
  };
  useEffect(() => {
    const t = setTimeout(() => void load(), 200);
    return () => clearTimeout(t);
  }, [q, mode, api]); // eslint-disable-line react-hooks/exhaustive-deps

  const shown = useMemo(() => {
    if (range === "all") return items;
    const days = Number(range);
    const cutoff = Date.now() - days * 86_400_000;
    return items.filter((s) => parse(s.updated_at).getTime() >= cutoff);
  }, [items, range]);

  const create = async () => {
    if (mode === "interview") return setPage("interview");
    await newSession(mode);
    setPage(folder.page);
  };

  return (
    <div>
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft size={15} /> Folders
        </Button>
        <div>
          <h2 className="text-xl font-semibold text-espresso">{folder.title}</h2>
          <p className="text-xs text-caramel">Explore, open and manage your sessions.</p>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <div className="relative w-72">
          <Search size={14} className="absolute top-3 left-3 text-sand" />
          <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by title or content" className="pl-9" aria-label="Search this folder" />
        </div>
        <Select value={range} onChange={(e) => setRange(e.target.value)} className="w-40" aria-label="Date range">
          <option value="all">Any date</option>
          <option value="1">Last 24 hours</option>
          <option value="7">Last 7 days</option>
          <option value="30">Last 30 days</option>
        </Select>
      </div>
      <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        <button type="button" onClick={() => void create()} className="flex min-h-40 flex-col items-center justify-center rounded-[var(--radius-card)] bg-caramel p-5 text-white shadow-[var(--shadow-lift)] hover:bg-mocha">
          <Plus size={26} />
          <span className="mt-2 text-sm font-semibold">Create new</span>
          <span className="text-xs opacity-80">Start a new {folder.unit.replace(/s$/, "")}</span>
        </button>
        {shown.map((s) => (
          <Card key={s.id} className="group relative flex min-h-40 flex-col p-4">
            <button type="button" onClick={() => void openSession(s.id)} className="flex flex-1 flex-col text-left" aria-label={`Open ${s.title}`}>
              <span className="text-[11px] text-caramel">{parse(s.updated_at).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}</span>
              <span className="mt-1 line-clamp-2 text-sm font-semibold text-espresso">{s.title}</span>
              <span className="mt-1 line-clamp-3 text-xs leading-relaxed text-mocha">{s.summary?.replace(/[#*|>-]/g, " ") || `${s.message_count ?? 0} messages`}</span>
              <span className="mt-auto pt-3">
                <Badge tone="outline">
                  <folder.icon size={11} /> {folder.title}
                </Badge>
              </span>
            </button>
            <button
              type="button"
              aria-label={`Delete ${s.title}`}
              onClick={async () => {
                if (!confirm(`Delete "${s.title}"? This cannot be undone.`)) return;
                await deleteSession(s.id);
                await load();
              }}
              className="absolute top-3 right-3 hidden text-sand group-hover:block hover:text-bark"
            >
              <Trash2 size={14} />
            </button>
          </Card>
        ))}
      </div>
      {shown.length === 0 && <p className="mt-6 text-sm text-caramel">{q || range !== "all" ? "Nothing matches." : "This folder is empty."}</p>}
    </div>
  );
}

export function Library() {
  const { api, collections, setPage, sessions } = useApp();
  const [open, setOpen] = useState<Mode | null>(null);
  const [byMode, setByMode] = useState<Record<string, Session[]>>({});

  useEffect(() => {
    if (!api) return;
    void Promise.all(FOLDERS.map((f) => api.get<Session[]>(`/api/sessions?mode=${f.mode}`))).then((lists) =>
      setByMode(Object.fromEntries(FOLDERS.map((f, i) => [f.mode, lists[i]]))),
    );
  }, [api, sessions.length, open]);

  return (
    <div className="flex h-full flex-col">
      <TopBar title="Library" subtitle="Every session and document, stored on this computer" />
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-6xl px-6 py-8">
          {open ? (
            <NotesGrid mode={open} onBack={() => setOpen(null)} />
          ) : (
            <>
              <h2 className="text-center text-2xl font-semibold text-espresso">Folders</h2>
              <div className="mt-8 grid justify-items-center gap-10 sm:grid-cols-2 lg:grid-cols-3">
                {FOLDERS.map((f) => (
                  <FolderCard
                    key={f.mode}
                    title={f.title}
                    unit={f.unit}
                    icon={f.icon}
                    count={byMode[f.mode]?.length ?? 0}
                    peek={(byMode[f.mode] ?? []).map((s) => s.title)}
                    onOpen={() => setOpen(f.mode)}
                  />
                ))}
                <FolderCard
                  title="Knowledge"
                  unit="collections"
                  icon={BookOpen}
                  count={collections.length}
                  peek={collections.map((c) => `${c.name} · ${c.documents.length} files`)}
                  onOpen={() => setPage("knowledge")}
                />
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
