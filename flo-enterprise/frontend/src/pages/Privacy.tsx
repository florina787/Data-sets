import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Badge, Button, Card, ErrorState, Input, Label, PageHeader, Select } from "@/components/ui";
import { api } from "@/lib/api";
import { useApp } from "@/lib/app";

export default function Privacy() {
  const { can } = useApp();
  const [text, setText] = useState("Client Sarah Williams has account 123456789. Email sarah.w@example.com, phone +1-416-555-0123.");
  const [purpose, setPurpose] = useState("privacy_request");
  const scan = useMutation({ mutationFn: () => api("/api/privacy/scan", { method: "POST", json: { text } }) });
  const tok = useMutation({ mutationFn: () => api("/api/privacy/tokenize", { method: "POST", json: { text } }) });
  const reh = useMutation({ mutationFn: () => api("/api/privacy/rehydrate", { method: "POST", json: { text: tok.data.text, scope: tok.data.scope, purpose } }) });
  const [erase, setErase] = useState({ entity_type: "EMAIL", value: "" });
  const er = useMutation({ mutationFn: () => api("/api/privacy/erase", { method: "POST", json: erase }) });
  const purge = useMutation({ mutationFn: () => api("/api/privacy/purge-expired", { method: "POST" }) });
  return (
    <div className="space-y-4">
      <PageHeader title="Privacy Console" subtitle="Detection (patterns + validators + CRM gazetteer; Presidio when installed), masking, tokenization into an encrypted vault, authorized rehydration, retention and secure deletion." />
      <Card className="space-y-3 p-4">
        <textarea className="w-full rounded-md border border-line bg-bg p-2 text-sm" rows={3} value={text} onChange={(e) => setText(e.target.value)} aria-label="Text to analyse" />
        <div className="flex flex-wrap gap-2"><Button onClick={() => scan.mutate()}>Detect</Button><Button variant="primary" onClick={() => tok.mutate()}>Tokenize</Button>
          {tok.data && can("privacy:rehydrate") && <><Select value={purpose} onChange={(e) => setPurpose(e.target.value)} aria-label="Purpose"><option value="privacy_request">privacy_request</option><option value="compliance_review">compliance_review</option><option value="">(none)</option></Select>
            <Button variant="blue" onClick={() => reh.mutate()}>Rehydrate (policy-checked)</Button></>}</div>
        {scan.data && <div className="flex flex-wrap gap-1">{scan.data.findings.map((f: any, i: number) => <Badge key={i} tone="warn">{f.type}: {f.masked} ({f.recognizer})</Badge>)}</div>}
        {tok.data && <div className="text-sm"><Label>Tokenized (scope {tok.data.scope})</Label><pre className="whitespace-pre-wrap rounded-md border border-line bg-bg p-2">{tok.data.text}</pre></div>}
        {reh.data && <div className="text-sm"><Label>Rehydrated</Label><pre className="whitespace-pre-wrap rounded-md border border-line bg-bg p-2">{reh.data.text}</pre>
          <div className="text-xs text-muted">restored {reh.data.restored.length}, denied {reh.data.denied.map((d: any) => `${d.token}(${d.reason})`).join(", ") || "none"}</div></div>}
        {(scan.error || tok.error || reh.error) && <ErrorState error={scan.error || tok.error || reh.error} />}
        <p className="text-[11px] text-muted">Token mappings never leave the server; the UI only sees tokens. Pseudonymized data is still treated as personal information.</p>
      </Card>
      {can("privacy:admin") && (
        <Card className="space-y-2 p-4"><h3 className="text-sm font-semibold">Secure deletion & retention</h3>
          <div className="flex flex-wrap items-end gap-2"><div><Label>Entity type</Label><Select value={erase.entity_type} onChange={(e) => setErase({ ...erase, entity_type: e.target.value })}>{["PERSON", "EMAIL", "PHONE", "SIN", "ACCOUNT", "CLIENT_ID", "DOB", "ADDRESS"].map((x) => <option key={x}>{x}</option>)}</Select></div>
            <div className="flex-1"><Label>Value</Label><Input value={erase.value} onChange={(e) => setErase({ ...erase, value: e.target.value })} /></div>
            <Button variant="danger" onClick={() => er.mutate()} disabled={!erase.value}>Erase subject mappings</Button><Button onClick={() => purge.mutate()}>Purge expired</Button></div>
          {er.data && <p className="text-xs">Erased {er.data.mappings_erased} mapping(s).</p>}{purge.data && <p className="text-xs">Purged {purge.data.purged} expired mapping(s).</p>}
        </Card>
      )}
    </div>
  );
}
