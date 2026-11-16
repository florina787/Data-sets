import { useEffect, useState } from "react";
import { Trash2, Download } from "lucide-react";
import { useApp } from "../lib/app-state";
import { PROFILES, STAGE_LABEL, INTEREST_OPTIONS, type Stage } from "../data/examples/profiles";
import { resetDemo } from "../lib/storage";
import { usePersistent } from "../lib/usePersistent";
import { Badge, Button, Card, Field, Notice, PageHeader, inputCls } from "../components/ui";
import { CATEGORY_LABEL, type NotifCategory } from "../modules/notifications/engine";
import { REGIONS } from "../modules/nutrition/foods";
import { DEFAULT_LLAMA, llamaProvider, testLlama, type LlamaConfig } from "../modules/conversation/llamaProvider";
import { setProvider } from "../modules/conversation/router";
import { scriptedProvider } from "../modules/conversation/scriptedProvider";

function exportAll() {
  const data = Object.fromEntries(Object.keys(localStorage).filter((k) => k.startsWith("femora:")).map((k) => [k, JSON.parse(localStorage.getItem(k) ?? "null")]));
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }));
  const a = document.createElement("a"); a.href = url; a.download = "femora-muse-data.json"; a.click(); URL.revokeObjectURL(url);
}

export function Settings() {
  const app = useApp();
  const p = app.profile;
  const [llama, setLlama] = usePersistent<LlamaConfig>("llama", () => DEFAULT_LLAMA);
  const [status, setStatus] = useState<string | null>(null);
  const [perm, setPerm] = useState(typeof Notification === "undefined" ? "unsupported" : Notification.permission);
  useEffect(() => { setProvider(llama.enabled ? llamaProvider(llama) : scriptedProvider); }, [llama]);
  const cat = (c: NotifCategory, patch: Partial<typeof app.prefs.categories.health>) => app.setPrefs({ ...app.prefs, categories: { ...app.prefs.categories, [c]: { ...app.prefs.categories[c], ...patch } } });

  return (
    <div className="space-y-5">
      <PageHeader title="Profile, privacy & preferences" sub="Everything here is optional and stays in this browser. Muse uses only what you choose to share." />

      <Card title="Profile" actions={<label className="flex items-center gap-2 text-sm text-muted">Example configuration
        <select className="rounded-full border border-line bg-surface px-3 py-1" value={p.id} onChange={(e) => app.setProfileId(e.target.value)}>{PROFILES.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></label>}>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <Field label="Name"><input className={inputCls} value={p.name} onChange={(e) => app.updateProfile({ name: e.target.value })} /></Field>
          <Field label="Age (optional)"><input type="number" min={0} className={inputCls} value={p.age || ""} onChange={(e) => app.updateProfile({ age: Number(e.target.value) })} /></Field>
          <Field label="Country"><input className={inputCls} value={p.country} onChange={(e) => app.updateProfile({ country: e.target.value })} /></Field>
          <Field label="City"><input className={inputCls} value={app.location?.city ?? p.city} onChange={(e) => { app.updateProfile({ city: e.target.value }); app.setLocation({ region: app.location?.region ?? "North America", city: e.target.value }); }} /></Field>
          <Field label="Region"><select className={inputCls} value={app.location?.region ?? ""} onChange={(e) => app.setLocation({ region: e.target.value, city: app.location?.city ?? p.city })}><option value="">Not set</option>{REGIONS.filter((r) => r !== "Universal").map((r) => <option key={r}>{r}</option>)}</select></Field>
          <Field label="Life stage (optional)" hint="Muse never infers this"><select className={inputCls} value={p.stage ?? ""} onChange={(e) => app.updateProfile({ stage: (e.target.value || undefined) as Stage | undefined })}><option value="">Prefer not to say</option>{Object.entries(STAGE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
        </div>
        <div className="mt-4"><span className="text-sm font-medium">Interests</span>
          <div className="mt-1 flex flex-wrap gap-2">{INTEREST_OPTIONS.map((i) => { const on = p.interests.includes(i); return <button key={i} aria-pressed={on} onClick={() => app.updateProfile({ interests: on ? p.interests.filter((x) => x !== i) : [...p.interests, i] })} className={`rounded-full px-3 py-1.5 text-sm ${on ? "bg-primary text-primary-ink" : "bg-surface-2"}`}>{i}</button>; })}</div></div>
        <div className="mt-4"><span className="text-sm font-medium">Favourite cuisines</span>
          <div className="mt-1 flex flex-wrap gap-2">{REGIONS.filter((r) => r !== "Universal").map((r) => { const on = p.cuisine.includes(r); return <button key={r} aria-pressed={on} onClick={() => app.updateProfile({ cuisine: on ? p.cuisine.filter((x) => x !== r) : [...p.cuisine, r] })} className={`rounded-full px-3 py-1.5 text-sm ${on ? "bg-accent text-white" : "bg-surface-2"}`}>{r}</button>; })}</div></div>
      </Card>

      <Card title="Notifications">
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <span>Browser alerts: <Badge tone={perm === "granted" ? "good" : "neutral"}>{perm}</Badge></span>
          {perm !== "granted" && perm !== "unsupported" && <Button size="sm" onClick={async () => { const r = await Notification.requestPermission(); setPerm(r); if (r === "granted") app.setPrefs({ ...app.prefs, browserNotifications: true }); }}>Allow browser alerts</Button>}
          {perm === "granted" && <label className="flex items-center gap-2"><input type="checkbox" checked={app.prefs.browserNotifications} onChange={(e) => app.setPrefs({ ...app.prefs, browserNotifications: e.target.checked })} /> Use browser alerts</label>}
          <label className="flex items-center gap-2"><input type="checkbox" checked={app.prefs.privateMedication} onChange={(e) => app.setPrefs({ ...app.prefs, privateMedication: e.target.checked })} /> Hide medication and appointment details in alerts</label>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
          <label className="flex items-center gap-2"><input type="checkbox" checked={app.prefs.quietHours.enabled} onChange={(e) => app.setPrefs({ ...app.prefs, quietHours: { ...app.prefs.quietHours, enabled: e.target.checked } })} /> Quiet hours</label>
          <input aria-label="Quiet hours start" type="time" className={inputCls + " !w-32 !py-1"} value={app.prefs.quietHours.start} onChange={(e) => app.setPrefs({ ...app.prefs, quietHours: { ...app.prefs.quietHours, start: e.target.value } })} /> to
          <input aria-label="Quiet hours end" type="time" className={inputCls + " !w-32 !py-1"} value={app.prefs.quietHours.end} onChange={(e) => app.setPrefs({ ...app.prefs, quietHours: { ...app.prefs.quietHours, end: e.target.value } })} />
        </div>
        <table className="mt-4 w-full text-sm"><thead><tr className="text-left text-muted"><th className="py-1">Category</th><th>On</th><th>Delivery</th><th>Max per day</th></tr></thead>
          <tbody>{(Object.keys(CATEGORY_LABEL) as NotifCategory[]).map((c) => { const v = app.prefs.categories[c]; return (
            <tr key={c} className="border-t border-line"><td className="py-2">{CATEGORY_LABEL[c]}</td>
              <td><input type="checkbox" aria-label={`${CATEGORY_LABEL[c]} on`} checked={v.enabled} onChange={(e) => cat(c, { enabled: e.target.checked })} /></td>
              <td><select aria-label={`${CATEGORY_LABEL[c]} delivery`} className="rounded border border-line bg-surface px-2 py-1" value={v.mode} onChange={(e) => cat(c, { mode: e.target.value as "immediate" | "digest" })}><option value="immediate">Immediate</option><option value="digest">Daily digest</option></select></td>
              <td><input type="number" min={1} max={50} aria-label={`${CATEGORY_LABEL[c]} limit`} className="w-16 rounded border border-line bg-surface px-2 py-1" value={v.maxPerDay} onChange={(e) => cat(c, { maxPerDay: Math.max(1, Number(e.target.value)) })} /></td></tr>); })}</tbody></table>
        <p className="mt-2 text-xs text-muted">Critical safety alerts always come through. Quiet hours move everything else to your digest. Marking alerts "not relevant" teaches Muse to send fewer of that kind.</p>
      </Card>

      <Card title="Muse model">
        <p className="text-sm text-muted">Muse works offline with its own reviewed responses. For open conversation, connect a model running on your own computer with <b>llama.cpp</b> (e.g. <code>llama-server -m model.gguf --port 8080</code>). Your conversations go only to that server.</p>
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <Field label="llama.cpp server URL"><input className={inputCls + " !w-72"} value={llama.url} onChange={(e) => setLlama({ ...llama, url: e.target.value, enabled: false })} /></Field>
          <Button onClick={async () => { setStatus("Testing…"); try { const m = await testLlama(llama.url); setStatus(`Connected: ${m}`); } catch (e) { setStatus(`Not reachable: ${(e as Error).message}`); setLlama({ ...llama, enabled: false }); } }}>Test connection</Button>
          <label className="flex items-center gap-2 pb-2 text-sm"><input type="checkbox" checked={llama.enabled} disabled={!status?.startsWith("Connected") && !llama.enabled} onChange={(e) => setLlama({ ...llama, enabled: e.target.checked })} /> Use this model</label>
        </div>
        {status && <p className="mt-2 text-sm" role="status">{status}</p>}
        <p className="mt-2 text-xs text-muted">Safety rules, reminders and all numbers stay deterministic; the model only writes conversation. If the server stops, Muse falls back to offline mode.</p>
      </Card>

      <Card title="Memory" actions={<label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={app.memoryEnabled} onChange={(e) => app.setMemoryEnabled(e.target.checked)} /> Allow Muse to remember approved facts</label>}>
        {app.memory.length === 0 ? <p className="text-sm text-muted">No saved memories. Muse asks before remembering anything.</p> : (
          <ul className="divide-y divide-line">{app.memory.map((m) => (
            <li key={m.id} className="flex items-center justify-between py-2 text-sm">{m.text}<button aria-label={`Forget ${m.text}`} className="text-muted hover:text-danger" onClick={() => app.removeMemory(m.id)}><Trash2 size={15} /></button></li>))}</ul>)}
      </Card>

      <Card title="Your data">
        <Notice tone="warn">Data is stored in this browser's local storage, which isn't encrypted. Encrypted storage and secure sync come with accounts and the mobile app.</Notice>
        <div className="mt-3 flex flex-wrap gap-2"><Button onClick={exportAll}><Download size={16} /> Export my data</Button>
          <Button variant="danger" onClick={() => { if (confirm("Delete all FEMORA Muse data in this browser? This can't be undone.")) { resetDemo(); location.reload(); } }}><Trash2 size={16} /> Delete all my data</Button></div>
      </Card>
    </div>
  );
}
