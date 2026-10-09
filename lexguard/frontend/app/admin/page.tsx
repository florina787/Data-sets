"use client";

import { Badge, ErrorBox, LoadingBlock, PageHead, Panel, StatusPill } from "@/components/ui";
import { useApi } from "@/hooks/useApi";
import { useAppState } from "@/hooks/useAppState";
import { humanize } from "@/lib/format";

export default function AdminPage() {
  const { userId } = useAppState();
  const cfg = useApi<any>("/config", null);
  const me = useApi<any>("/me", userId);
  const users = useApi<any[]>("/users", null);
  const providers = useApi<any[]>("/providers", userId);
  const agents = useApi<any[]>("/agents", null);
  return (
    <div className="page">
      <PageHead title="Admin / Configuration" description="Runtime configuration (secrets are never displayed), identities and roles, provider registry and agent catalogue." />
      <ErrorBox error={cfg.error} />
      <div className="grid grid-2">
        <Panel title="Runtime configuration">{cfg.loading && !cfg.data ? <LoadingBlock /> : cfg.data && (
          <table className="table"><tbody>{Object.entries(cfg.data).map(([k, v]) => <tr key={k}><td className="small">{humanize(k)}</td><td className="mono small">{String(v)}</td></tr>)}</tbody></table>)}
          <div className="notice" style={{ marginTop: 8 }}>DEMO_MODE requires no API key and makes zero paid LLM calls. Live mode reads ANTHROPIC_API_KEY from the environment only; the LLM may rephrase answers but never makes control decisions.</div>
        </Panel>
        <Panel title="Signed-in identity">{me.data && (<div className="stack">
          <div><span className="strong">{me.data.name}</span> · {humanize(me.data.role)}</div>
          <div className="row">{me.data.permissions.map((p: string) => <Badge key={p} tone="good">{p}</Badge>)}</div>
          <div className="tiny muted">Demo identity is selected with the X-LexGuard-User header. Production would use SSO/OIDC; every control uses the resolved identity only.</div></div>)}</Panel>
      </div>
      <div style={{ marginTop: 12 }}><Panel title="Users & roles (synthetic)" bodyClass="table-wrap">
        <table className="table"><thead><tr><th>User</th><th>Role</th><th>Practice</th><th>Email</th></tr></thead>
          <tbody>{(users.data ?? []).map((u) => <tr key={u.user_id}><td className="small strong">{u.name} <span className="mono tiny muted">{u.user_id}</span></td>
            <td>{humanize(u.role)}</td><td>{u.practice ?? "Firm-wide"}</td><td className="mono tiny">{u.email}</td></tr>)}</tbody></table></Panel></div>
      <div style={{ marginTop: 12 }}><Panel title="Provider registry" bodyClass="table-wrap">
        <table className="table"><thead><tr><th>Provider</th><th>Type</th><th>Approval</th><th>Status</th><th>Allowed classifications</th><th>Notes</th></tr></thead>
          <tbody>{(providers.data ?? []).map((p) => <tr key={p.provider_id}><td className="small strong">{p.name}<div className="mono tiny muted">{p.provider_id}</div></td>
            <td className="small">{humanize(p.type)} · {p.external ? "external" : "internal"}</td><td><StatusPill status={p.approval_status === "APPROVED" ? "APPROVED" : "RESTRICTED"} label={p.approval_status} /></td>
            <td className="small">{p.status}</td><td className="tiny">{p.allowed_classifications.join(", ") || "—"}</td><td className="tiny">{p.notes}</td></tr>)}</tbody></table></Panel></div>
      <div style={{ marginTop: 12 }}><Panel title="Agent catalogue (backend intelligence - not user-facing chatbots)" bodyClass="table-wrap">
        <table className="table"><thead><tr><th>Agent</th><th>Version</th><th>Tool allowlist</th></tr></thead>
          <tbody>{(agents.data ?? []).map((a) => <tr key={a.agent_id}><td><div className="small strong">{a.name}</div><div className="tiny muted">{a.description}</div></td>
            <td className="mono small">{a.version}</td><td>{a.tools.length ? a.tools.map((t: string) => <Badge key={t} tone="neutral">{t}</Badge>) : <span className="tiny muted">no tools (control-plane)</span>}</td></tr>)}</tbody></table></Panel></div>
    </div>
  );
}
