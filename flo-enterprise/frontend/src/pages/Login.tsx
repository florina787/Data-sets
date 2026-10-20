import { useQuery } from "@tanstack/react-query";
import { Building2, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { api } from "@/lib/api";
import { useApp } from "@/lib/app";
import { Badge, Card, ErrorState, Spinner } from "@/components/ui";

export default function Login() {
  const { login } = useApp();
  const users = useQuery({ queryKey: ["demo-users"], queryFn: () => api("/api/auth/users") });
  const [err, setErr] = useState<unknown>(null);
  return (
    <div className="grid min-h-full place-items-center p-6">
      <div className="w-full max-w-3xl space-y-4">
        <div className="flex items-center gap-3">
          <div className="grid h-12 w-12 place-items-center rounded-xl bg-card ring-1 ring-gold/50"><Building2 className="h-6 w-6 text-gold" /></div>
          <div><h1 className="text-2xl font-semibold">FLO Enterprise</h1><p className="text-sm text-muted">Financial Leadership, Operations &amp; Wealth Intelligence</p></div>
        </div>
        <Card className="p-4 text-sm text-muted">
          Independent architecture demonstration. Not affiliated with any asset manager. All data is <b className="text-gold">synthetic</b>; integrations are mock adapters;
          the identity provider is a mock that issues short-lived tokens for the synthetic users below. Trading is prohibited.
        </Card>
        {users.isLoading && <Spinner />}
        {(users.error || err) && <ErrorState error={users.error || err} />}
        <div className="grid gap-3 sm:grid-cols-2">
          {users.data?.users.map((u: any) => (
            <button key={u.id} data-user={u.id} onClick={() => login(u.id).catch(setErr)}
              className="rounded-xl border border-line bg-card p-4 text-left hover:border-gold focus:border-gold">
              <div className="font-medium">{u.display_name}</div>
              <div className="text-xs text-muted">{u.title} · {u.tenant_id}</div>
              <div className="mt-2 flex flex-wrap gap-1">{u.roles.map((r: string) => <Badge key={r} tone="blue">{r}</Badge>)}</div>
            </button>
          ))}
        </div>
        <p className="flex items-center gap-1 text-xs text-muted"><ShieldCheck className="h-3.5 w-3.5" />Every request is authorized server-side (deny by default) and audited.</p>
      </div>
    </div>
  );
}
