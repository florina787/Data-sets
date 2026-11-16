import { Trash2 } from "lucide-react";
import { useApp } from "../lib/app-state";
import { PROFILES, STAGE_LABEL } from "../data/demo/profiles";
import { resetDemo } from "../lib/storage";
import { Badge, Button, Card, Notice, PageHeader } from "../components/ui";

export function Settings() {
  const app = useApp();
  return (
    <div className="space-y-5">
      <PageHeader title="Profile & privacy" status="demonstrated" sub="Switch fictional demo profiles, change the theme, and control what FEMORA remembers." />
      <Card title="Demo profiles (fictional)">
        <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
          {PROFILES.map((p) => (
            <button key={p.id} onClick={() => app.setProfileId(p.id)} aria-pressed={p.id === app.profile.id}
              className={`rounded-f-sm border p-3 text-left ${p.id === app.profile.id ? "border-primary ring-2 ring-primary/30" : "border-line hover:bg-surface-2"}`}>
              <b>{p.name}, {p.age}</b> <span className="text-sm text-muted">· {[p.city, p.country].filter(Boolean).join(", ")}</span>
              <div className="mt-1 flex flex-wrap gap-1"><Badge tone="accent">{STAGE_LABEL[p.stage]}</Badge><Badge>{p.diet}</Badge>{p.livesAlone && <Badge>Lives alone</Badge>}</div>
              <p className="mt-1 text-sm text-muted">{p.story}</p>
            </button>))}
        </div>
      </Card>
      <Card title="Memory" actions={<label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={app.memoryEnabled} onChange={(e) => app.setMemoryEnabled(e.target.checked)} /> Allow FEMORA to remember approved facts</label>}>
        <p className="text-sm text-muted">FEMORA only remembers things you approve. Session context is used within a conversation and is not stored as memory.</p>
        {app.memory.length === 0 ? <p className="mt-2 text-sm">No saved memories.</p> : (
          <ul className="mt-2 divide-y divide-line">{app.memory.map((m) => (
            <li key={m.id} className="flex items-center justify-between py-2 text-sm">{m.text}<button aria-label={`Forget ${m.text}`} className="text-muted hover:text-danger" onClick={() => app.removeMemory(m.id)}><Trash2 size={15} /></button></li>))}</ul>)}
      </Card>
      <Card title="Where your demo data lives">
        <Notice tone="warn">Everything you enter is stored only in this browser's local storage, unencrypted, on this device. Don't enter real health information into this public demo.</Notice>
        <Button variant="danger" className="mt-3" onClick={() => { if (confirm("Reset all demo data in this browser?")) { resetDemo(); location.reload(); } }}>Reset demo</Button>
      </Card>
    </div>
  );
}
