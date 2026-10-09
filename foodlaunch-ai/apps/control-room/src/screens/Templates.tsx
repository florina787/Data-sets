import { Card, Empty, Notice, Status } from "../components/ui";
import { usePoll } from "../hooks";

export default function Templates() {
  const { data, error } = usePoll<any>("/api/templates", 60000);
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">Scenario templates</h1>
      <Notice kind="info">
        Only the flagship Ontario buy-2-get-1 scenario is implemented end to end. The templates below are reusable briefs,
        clarification checklists, requirements and test plans, shown as previews. They are <b>not</b> implemented as working applications.
      </Notice>
      {error && <Notice kind="error">{error}</Notice>}
      {!data ? <Empty>Loading…</Empty> : (
        <div className="grid gap-4 lg:grid-cols-2">
          {data.templates.map((t: any) => (
            <Card key={t.id} title={t.title} actions={<Status value="template only" />}>
              <blockquote className="border-l-4 border-cream-300 pl-3 text-sm italic">{t.brief}</blockquote>
              <h3 className="label mt-3">Clarifications to resolve</h3>
              <ul className="list-disc pl-5 text-sm">{t.clarifications.map((c: string) => <li key={c}>{c}</li>)}</ul>
              <h3 className="label mt-3">Requirements</h3>
              {t.requirements.map((r: any) => (
                <div key={r.id} className="text-sm"><b>{r.id}</b> {r.title}<ul className="list-disc pl-5 text-xs">{r.criteria.map((c: string) => <li key={c}>{c}</li>)}</ul></div>
              ))}
              <h3 className="label mt-3">Test plan</h3>
              <ul className="list-disc pl-5 text-xs">{t.test_plan.map((c: string) => <li key={c}>{c}</li>)}</ul>
              <p className="mt-2 text-xs text-navy-600">Risks: {t.risks.join("; ")}. {t.implementation_note}</p>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
