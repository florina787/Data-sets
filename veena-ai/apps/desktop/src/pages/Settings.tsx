import { Download, RefreshCw, RotateCcw, Trash2, Wand2 } from "lucide-react";
import { useEffect, useState } from "react";
import { ANSWER_STYLES } from "../components/Composer";
import { TopBar } from "../components/Shell";
import { Badge, Button, Card, CardHeader, Input, Select, Switch } from "../components/ui";
import { useApp } from "../stores/app";
import { useAudio } from "../stores/media";
import { HardwareCard, useHardware, usePull } from "./Setup";

const WHISPER = ["tiny", "base", "small", "medium", "large-v3", "distil-large-v3"];

function Row({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[1fr_260px] items-center gap-4 border-t border-cream px-5 py-3 first:border-t-0">
      <div>
        <p className="text-sm font-medium text-bark">{label}</p>
        {hint && <p className="text-xs text-caramel">{hint}</p>}
      </div>
      <div>{children}</div>
    </div>
  );
}

function Diagnostics() {
  const { api, backend } = useApp();
  const [m, setM] = useState<{ live: Record<string, { count: number; p50?: number; p95?: number }>; resources: Record<string, unknown> } | null>(null);
  const [log, setLog] = useState("");
  useEffect(() => {
    const load = async () => api && setM(await api.get("/api/metrics?days=1"));
    void load();
    const t = setInterval(() => void load(), 3000);
    return () => clearInterval(t);
  }, [api]);
  const r = m?.resources as { system_cpu_percent: number; system_ram_used_gb: number; system_ram_total_gb: number; backend_rss_mb: number; backend_cpu_percent: number; gpu: { name: string; util_percent: number; mem_used_mb: number }[] | null } | undefined;
  return (
    <Card>
      <CardHeader
        title="Developer diagnostics"
        subtitle={`Backend ${backend?.status} at ${backend?.url}`}
        actions={
          <div className="flex gap-1">
            <Button size="sm" variant="ghost" onClick={async () => setLog(await window.veena!.backendLog())}>
              Show log
            </Button>
            <Button size="sm" variant="ghost" onClick={() => void window.veena!.restartBackend()}>
              <RotateCcw size={14} /> Restart backend
            </Button>
          </div>
        }
      />
      {r && (
        <div className="grid grid-cols-4 gap-3 p-5 text-sm">
          {[
            ["System CPU", `${r.system_cpu_percent.toFixed(0)}%`],
            ["System RAM", `${r.system_ram_used_gb} / ${r.system_ram_total_gb} GB`],
            ["Backend RAM", `${r.backend_rss_mb} MB`],
            ["GPU", r.gpu?.length ? `${r.gpu[0].util_percent}% · ${r.gpu[0].mem_used_mb} MB` : "not in use"],
          ].map(([k, v]) => (
            <div key={k} className="rounded-xl bg-warm p-3">
              <p className="text-xs text-caramel">{k}</p>
              <p className="text-bark tabular-nums">{v}</p>
            </div>
          ))}
        </div>
      )}
      <table className="mx-5 mb-5 w-[calc(100%-2.5rem)] text-sm">
        <thead>
          <tr className="text-left text-xs text-caramel">
            <th className="pb-1 font-medium">Metric (this run)</th>
            <th className="pb-1 font-medium">n</th>
            <th className="pb-1 font-medium">p50</th>
            <th className="pb-1 font-medium">p95</th>
          </tr>
        </thead>
        <tbody>
          {m &&
            Object.entries(m.live).map(([k, v]) => (
              <tr key={k} className="border-t border-cream text-bark">
                <td className="py-1 font-mono text-xs">{k}</td>
                <td className="tabular-nums">{v.count}</td>
                <td className="tabular-nums">{v.p50?.toFixed(1)}</td>
                <td className="tabular-nums">{v.p95?.toFixed(1)}</td>
              </tr>
            ))}
          {m && Object.keys(m.live).length === 0 && (
            <tr>
              <td colSpan={4} className="py-2 text-xs text-caramel">
                Nothing measured in this run yet.
              </td>
            </tr>
          )}
        </tbody>
      </table>
      {log && <pre className="mx-5 mb-5 max-h-64 overflow-auto rounded-xl bg-espresso p-3 font-mono text-[11px] text-cream">{log}</pre>}
    </Card>
  );
}

export function Settings() {
  const { settings, updateSettings, status, refreshStatus, setPage, api, toast, loadSessions } = useApp();
  const audio = useAudio();
  const hw = useHardware();
  const { progress, pull } = usePull();
  const [pullName, setPullName] = useState("");
  useEffect(() => {
    void audio.refreshDevices();
  }, [audio.refreshDevices]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!settings) return null;
  const installed = status?.models ?? [];
  const set = (patch: Parameters<typeof updateSettings>[0]) => void updateSettings(patch);

  return (
    <div className="flex h-full flex-col">
      <TopBar
        title="Settings"
        actions={
          <Button size="sm" variant="ghost" onClick={() => setPage("setup")}>
            <Wand2 size={14} /> Run setup again
          </Button>
        }
      />
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-4xl space-y-6 px-6 py-6">
          <Card>
            <CardHeader title="Answers" />
            <div className="mt-3">
              <Row label="Default answer style">
                <Select value={settings.answer_style} onChange={(e) => set({ answer_style: e.target.value })}>
                  {ANSWER_STYLES.filter(([v]) => v !== "auto").map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </Select>
              </Row>
              <Row label="Conversation memory" hint="Previous turns sent as context">
                <Select value={settings.context_turns} onChange={(e) => set({ context_turns: Number(e.target.value) })}>
                  {[2, 4, 8, 12, 16].map((n) => (
                    <option key={n} value={n}>
                      {n} turns
                    </option>
                  ))}
                </Select>
              </Row>
              <Row label="Auto-answer spoken questions" hint="In conversation and screen sessions">
                <Switch checked={settings.auto_answer_questions} onChange={(v) => set({ auto_answer_questions: v })} label="" />
              </Row>
              <Row label="Ask the model about ambiguous utterances" hint="Rules handle clear questions; unclear ones go to the local model">
                <Switch checked={settings.question_escalation} onChange={(v) => set({ question_escalation: v })} label="" />
              </Row>
            </div>
          </Card>

          <Card>
            <CardHeader
              title="Local models"
              subtitle={status?.ollama.running ? `Ollama ${status.ollama.version} at ${status.ollama.url}` : "Ollama is not running"}
              actions={
                <Button size="sm" variant="ghost" onClick={() => void refreshStatus()}>
                  <RefreshCw size={14} /> Refresh
                </Button>
              }
            />
            <div className="mt-3">
              <Row label="Text model">
                <Select value={settings.text_model ?? ""} onChange={(e) => set({ text_model: e.target.value || null })}>
                  <option value="">Automatic</option>
                  {installed.map((m) => (
                    <option key={m.name} value={m.name}>
                      {m.name} {m.parameter_size ? `(${m.parameter_size})` : ""}
                    </option>
                  ))}
                </Select>
              </Row>
              <Row label="Vision model" hint="Only vision-capable models are listed">
                <Select value={settings.vision_model ?? ""} onChange={(e) => set({ vision_model: e.target.value || null })}>
                  <option value="">Automatic / OCR only</option>
                  {installed
                    .filter((m) => m.vision)
                    .map((m) => (
                      <option key={m.name} value={m.name}>
                        {m.name}
                      </option>
                    ))}
                </Select>
              </Row>
              <Row label="Download another model" hint="Any model from the Ollama library, e.g. qwen2.5:7b">
                <div className="flex gap-2">
                  <Input value={pullName} onChange={(e) => setPullName(e.target.value)} placeholder="model:tag" />
                  <Button onClick={() => void pull(pullName.trim())} disabled={!pullName.trim()}>
                    <Download size={14} />
                  </Button>
                </div>
                {pullName && progress[pullName.trim()] && (
                  <p className="mt-1 text-xs text-caramel">
                    {progress[pullName.trim()].status} {progress[pullName.trim()].pct != null ? `${progress[pullName.trim()].pct}%` : ""}
                  </p>
                )}
              </Row>
            </div>
            <ul className="flex flex-wrap gap-1.5 px-5 pb-5">
              {installed.map((m) => (
                <li key={m.name}>
                  <Badge tone="outline">
                    {m.name} · {(m.size_bytes / 1e9).toFixed(1)} GB{m.vision ? " · vision" : ""}
                  </Badge>
                </li>
              ))}
            </ul>
          </Card>

          <Card>
            <CardHeader title="Speech" subtitle="faster-whisper with Silero voice activity detection, on this computer" />
            <div className="mt-3">
              <Row label="Speech model" hint="Larger is more accurate and slower">
                <Select value={settings.asr_model} onChange={(e) => set({ asr_model: e.target.value })}>
                  {WHISPER.map((w) => (
                    <option key={w} value={w}>
                      {w}
                    </option>
                  ))}
                </Select>
              </Row>
              <Row label="Language" hint="Automatic detection works for most speech">
                <Select value={settings.asr_language ?? ""} onChange={(e) => set({ asr_language: e.target.value || null })}>
                  <option value="">Automatic</option>
                  {["en", "hi", "es", "fr", "de", "pt", "it", "ja", "zh", "ko", "ar", "ru"].map((l) => (
                    <option key={l} value={l}>
                      {l}
                    </option>
                  ))}
                </Select>
              </Row>
              <Row label="Microphone">
                <Select value={audio.deviceId ?? ""} onChange={(e) => audio.setDevice(e.target.value || undefined)} onFocus={() => void audio.refreshDevices()}>
                  <option value="">System default</option>
                  {audio.devices.map((d) => (
                    <option key={d.deviceId} value={d.deviceId}>
                      {d.label || `Microphone ${d.deviceId.slice(0, 6)}`}
                    </option>
                  ))}
                </Select>
              </Row>
            </div>
          </Card>

          <Card>
            <CardHeader title="Privacy" subtitle="Raw audio and screenshots are never stored. Text history stays in a local database." />
            <div className="mt-3">
              <Row label="Keep history for" hint="Older sessions are deleted automatically">
                <Select value={settings.retention_days} onChange={(e) => set({ retention_days: Number(e.target.value) })}>
                  {[
                    [1, "1 day"],
                    [7, "7 days"],
                    [30, "30 days"],
                    [90, "90 days"],
                    [365, "1 year"],
                    [0, "Until I delete it"],
                  ].map(([v, l]) => (
                    <option key={v} value={v}>
                      {l}
                    </option>
                  ))}
                </Select>
              </Row>
              <Row label="Redact secrets on screen" hint="Masks passwords, keys and tokens before analysis">
                <Switch checked={settings.redact_screens} onChange={(v) => set({ redact_screens: v })} label="" />
              </Row>
              <Row label="Pause continuous analysis on sensitive content">
                <Switch checked={settings.pause_on_sensitive} onChange={(v) => set({ pause_on_sensitive: v })} label="" />
              </Row>
              <Row label="Clear all history" hint="Deletes every session, transcript and metric. Knowledge collections are kept.">
                <Button
                  variant="danger"
                  onClick={async () => {
                    if (!confirm("Delete all conversation history? This cannot be undone.")) return;
                    const r = await api!.del<{ deleted_sessions: number }>("/api/sessions?confirm=true");
                    await loadSessions();
                    useApp.setState({ currentSession: null, messages: [], live: null });
                    toast("success", `Deleted ${r.deleted_sessions} sessions.`);
                  }}
                >
                  <Trash2 size={14} /> Clear all history
                </Button>
              </Row>
            </div>
            <p className="px-5 pb-5 text-xs text-caramel">Data folder: {status?.data_dir}</p>
          </Card>

          {hw && (
            <Card>
              <CardHeader title="Hardware" subtitle={`Profile: ${settings.profile ?? "not set"} · recommended ${hw.recommendation.profile}`} />
              <div className="p-5">
                <HardwareCard hw={hw} />
              </div>
            </Card>
          )}

          <Diagnostics />
        </div>
      </div>
    </div>
  );
}
