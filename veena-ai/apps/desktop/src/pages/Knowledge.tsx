import { FileText, FolderPlus, Search, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { CatMark } from "../components/CatMark";
import { TopBar } from "../components/Shell";
import { Badge, Button, Card, CardHeader, Input, Select } from "../components/ui";
import type { Citation } from "../services/api";
import { useApp } from "../stores/app";

const KINDS: [string, string][] = [
  ["general", "General knowledge"],
  ["resume", "Resume"],
  ["job", "Job descriptions"],
  ["project", "Projects"],
  ["docs", "Technical documentation"],
  ["meeting", "Meeting notes"],
];
const ACCEPT = ".pdf,.docx,.txt,.md,.markdown,.csv,.json";

export function Knowledge() {
  const { collections, api, loadCollections, toast, selectedCollections, toggleCollection } = useApp();
  const [name, setName] = useState("");
  const [kind, setKind] = useState("general");
  const [uploading, setUploading] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<(Citation & { snippet: string })[] | null>(null);
  const [searchMs, setSearchMs] = useState<number | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const target = useRef<string | null>(null);

  const create = async () => {
    if (!name.trim() || !api) return;
    await api.post("/api/knowledge/collections", { name, kind });
    setName("");
    await loadCollections();
  };

  const upload = async (collectionId: string, files: FileList | File[]) => {
    if (!api) return;
    for (const f of Array.from(files)) {
      setUploading(f.name);
      try {
        const r = await api.upload(collectionId, f);
        toast(r.duplicate ? "info" : "success", r.duplicate ? `${f.name} is already in this collection.` : `Indexed ${f.name} (${r.chunks} passages).`);
      } catch (e) {
        toast("error", `${f.name}: ${(e as Error).message}`);
      }
    }
    setUploading(null);
    await loadCollections();
  };

  const search = async () => {
    if (!api || !query.trim()) return;
    const r = await api.post<{ results: (Citation & { snippet: string })[]; retrieval_ms: number }>("/api/knowledge/search", {
      query,
      collection_ids: selectedCollections,
    });
    setResults(r.results);
    setSearchMs(r.retrieval_ms);
  };

  return (
    <div className="flex h-full flex-col">
      <TopBar title="Knowledge" subtitle="Local documents for evidence-grounded answers with citations" />
      <input
        ref={fileInput}
        type="file"
        multiple
        accept={ACCEPT}
        className="hidden"
        onChange={(e) => {
          if (e.target.files && target.current) void upload(target.current, e.target.files);
          e.target.value = "";
        }}
      />
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-5xl space-y-6 px-6 py-6">
          <Card>
            <CardHeader title="New collection" subtitle="Group related files: a resume, a job description, project docs, notes." />
            <div className="flex gap-2 p-5">
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Collection name" onKeyDown={(e) => e.key === "Enter" && void create()} aria-label="Collection name" />
              <Select value={kind} onChange={(e) => setKind(e.target.value)} className="w-56" aria-label="Collection type">
                {KINDS.map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </Select>
              <Button variant="primary" onClick={() => void create()} disabled={!name.trim()}>
                <FolderPlus size={15} /> Create
              </Button>
            </div>
          </Card>

          {collections.length === 0 ? (
            <div className="flex flex-col items-center py-12 text-center">
              <CatMark size={64} mood="idle" />
              <p className="mt-3 text-sm text-mocha">No collections yet. Create one, then add PDF, DOCX, TXT, Markdown, CSV or JSON files.</p>
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {collections.map((c) => (
                <Card
                  key={c.id}
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    void upload(c.id, e.dataTransfer.files);
                  }}
                >
                  <CardHeader
                    title={c.name}
                    subtitle={`${KINDS.find(([k]) => k === c.kind)?.[1] ?? c.kind} · ${c.documents.length} files · ${c.chunk_count} passages`}
                    actions={
                      <div className="flex items-center gap-1">
                        <label className="mr-1 flex items-center gap-1.5 text-xs text-mocha">
                          <input type="checkbox" checked={selectedCollections.includes(c.id)} onChange={() => toggleCollection(c.id)} className="accent-[#99613E]" />
                          Use in answers
                        </label>
                        <Button
                          size="icon"
                          variant="ghost"
                          aria-label={`Delete collection ${c.name}`}
                          onClick={async () => {
                            if (!confirm(`Delete collection "${c.name}" and its index?`)) return;
                            await api!.del(`/api/knowledge/collections/${c.id}`);
                            await loadCollections();
                          }}
                        >
                          <Trash2 size={15} />
                        </Button>
                      </div>
                    }
                  />
                  <ul className="mt-3 max-h-48 space-y-1 overflow-y-auto px-5">
                    {c.documents.map((d) => (
                      <li key={d.id} className="group flex items-center gap-2 text-sm text-bark">
                        <FileText size={14} className="shrink-0 text-caramel" />
                        <span className="truncate">{d.filename}</span>
                        <span className="ml-auto shrink-0 text-xs text-sand">{d.chunk_count} passages</span>
                        <button
                          type="button"
                          className="hidden text-sand group-hover:block hover:text-bark"
                          aria-label={`Remove ${d.filename}`}
                          onClick={async () => {
                            await api!.del(`/api/knowledge/documents/${d.id}`);
                            await loadCollections();
                          }}
                        >
                          <Trash2 size={13} />
                        </button>
                      </li>
                    ))}
                  </ul>
                  <div className="p-5">
                    <Button
                      variant="subtle"
                      className="w-full border border-dashed border-sand"
                      disabled={!!uploading}
                      onClick={() => {
                        target.current = c.id;
                        fileInput.current?.click();
                      }}
                    >
                      <Upload size={15} /> {uploading ? `Indexing ${uploading}…` : "Add files or drop them here"}
                    </Button>
                  </div>
                </Card>
              ))}
            </div>
          )}

          <Card>
            <CardHeader title="Test retrieval" subtitle={selectedCollections.length ? `Searching ${selectedCollections.length} selected collection(s)` : "Searching all collections"} />
            <div className="flex gap-2 p-5 pb-3">
              <Input value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && void search()} placeholder="e.g. Which projects used FAISS?" aria-label="Search query" />
              <Button onClick={() => void search()}>
                <Search size={15} /> Search
              </Button>
            </div>
            {results && (
              <div className="space-y-2 px-5 pb-5">
                <p className="text-xs text-caramel">
                  {results.length} result(s) in {searchMs?.toFixed(0)} ms. Passages below the relevance floor are not shown.
                </p>
                {results.map((r) => (
                  <div key={r.chunk_id} className="rounded-xl border border-cream bg-warm p-3">
                    <div className="mb-1 flex items-center gap-2 text-xs text-mocha">
                      <Badge>[{r.n}]</Badge> {r.filename}
                      {r.page ? `, p.${r.page}` : ""}
                      <span className="ml-auto">
                        score {r.score.toFixed(3)} (vector {r.vector_score.toFixed(3)}, keyword {r.lexical_score.toFixed(2)})
                      </span>
                    </div>
                    <p className="text-sm whitespace-pre-wrap text-bark">{r.snippet}</p>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
