import { useMutation, useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Badge, Button, Card, ErrorState, Input, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";

export default function Knowledge() {
  const [params] = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const [doc, setDoc] = useState<string | null>(null);
  const s = useMutation({ mutationFn: (query: string) => api("/api/docs/search", { method: "POST", json: { query, k: 8 } }) });
  const d = useQuery({ queryKey: ["doc", doc], queryFn: () => api(`/api/docs/${doc}`), enabled: !!doc });
  useEffect(() => { if (params.get("q")) s.mutate(params.get("q")!); }, [params]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="space-y-4">
      <PageHeader title="Knowledge Search" subtitle="Permission-aware hybrid retrieval (BM25 + embeddings). Documents you cannot access are excluded before ranking; retrieved text is evidence, never instructions." />
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (q.trim()) s.mutate(q); }}>
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="e.g. single issuer concentration limit, politique de communication…" aria-label="Search documents" />
        <Button variant="primary" type="submit"><Search className="h-4 w-4" />Search</Button>
      </form>
      {s.isPending && <Spinner />}{s.error && <ErrorState error={s.error} />}
      <div className="grid gap-4 xl:grid-cols-2">
        {s.data && <div className="space-y-2">
          <div className="text-xs text-muted">Language {s.data.language} · {s.data.candidates_considered} authorized chunks considered · {s.data.documents_excluded_by_authorization} documents excluded by authorization</div>
          {s.data.results.map((r: any) => (
            <Card key={r.chunk_id} className="cursor-pointer p-3 hover:border-gold" onClick={() => setDoc(r.document_id)}>
              <div className="flex flex-wrap items-center gap-1"><span className="text-sm font-medium">{r.title}</span><Badge>v{r.version}</Badge><Badge tone="blue">{r.classification}</Badge><Badge>{r.language}</Badge></div>
              <div className="text-xs text-muted">{r.document_id} · {r.section} · score {r.score}</div>
              <p className="mt-1 text-sm">{r.text.slice(0, 320)}</p>
            </Card>))}
          {s.data.results.length === 0 && <p className="text-sm text-muted">No authorized evidence found.</p>}
        </div>}
        {doc && <Card className="p-4">{d.isLoading ? <Spinner /> : d.error ? <ErrorState error={d.error} /> : (
          <div className="space-y-2"><h2 className="font-semibold">{d.data.title}</h2>
            <div className="text-xs text-muted">{d.data.id} v{d.data.version} · owner {d.data.owner} · {d.data.classification} · effective {d.data.effective_date}{d.data.expiry_date ? ` · expires ${d.data.expiry_date}` : ""} · {d.data.jurisdiction}</div>
            {d.data.sections.map((x: any, i: number) => <div key={i}><h3 className="text-sm font-semibold">{x.section}</h3><p className="whitespace-pre-wrap text-sm">{x.text}</p></div>)}</div>)}</Card>}
      </div>
    </div>
  );
}
