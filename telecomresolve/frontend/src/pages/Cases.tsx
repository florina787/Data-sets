import { FormEvent, useEffect, useState } from "react";
import { api, post } from "../api";
import { useSession } from "../App";
import { Card, Empty, ErrorNote, StatusChip } from "../components/ui";
import { fmtTime } from "../format";
import { go } from "../router";
import { CaseSummary } from "../types";

export function Cases() {
  const { can } = useSession();
  const [cases, setCases] = useState<CaseSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ account_id: "", title: "", complaint_text: "" });
  const load = () => api<CaseSummary[]>("/api/cases").then(setCases).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      const c = await post<CaseSummary>("/api/cases", form);
      go("workspace", c.id);
    } catch (err) { setError((err as Error).message); }
  };

  return (
    <div className="grid-2">
      <Card title="Cases in your scope">
        <ErrorNote error={error} />
        {cases === null ? <p>Loading…</p> : cases.length === 0 ? <Empty>No cases visible to this persona.</Empty> : (
          <div className="table-wrap">
            <table>
              <thead><tr><th scope="col">Case</th><th scope="col">Title</th><th scope="col">Status</th><th scope="col">Updated</th></tr></thead>
              <tbody>
                {cases.map((c) => (
                  <tr key={c.id}>
                    <td><a href={`#/workspace/${encodeURIComponent(c.id)}`}>{c.id}</a></td>
                    <td>{c.title}</td>
                    <td><StatusChip status={c.status} /></td>
                    <td>{fmtTime(c.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      {can("case:create") && (
        <Card title="New intake">
          <form onSubmit={submit} className="form">
            <label>Account ID<input required value={form.account_id} placeholder="e.g. ACCT-1003"
              onChange={(e) => setForm({ ...form, account_id: e.target.value })} /></label>
            <label>Title<input required minLength={3} value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })} /></label>
            <label>Customer complaint (as reported)<textarea required minLength={5} rows={4} value={form.complaint_text}
              onChange={(e) => setForm({ ...form, complaint_text: e.target.value })} /></label>
            <button className="btn" type="submit">Create case</button>
            <p className="muted small">New cases use a simulated post-action profile with a telemetry gap, so recovery
              will stay unverified unless more samples arrive.</p>
          </form>
        </Card>
      )}
    </div>
  );
}
