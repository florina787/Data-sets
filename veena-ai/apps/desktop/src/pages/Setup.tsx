import { Check, Cpu, Download, Gauge, HardDrive, MemoryStick, MonitorSmartphone } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { CatMark, Wordmark } from "../components/CatMark";
import { Badge, Button, Card, cn, Select } from "../components/ui";
import { readNdjson } from "../services/api";
import { useApp } from "../stores/app";

interface Profile {
  label: string;
  target: string;
  text_model: string;
  vision_model: string;
  asr_model: string;
  num_ctx: number;
  notes: string;
  download_gb: number;
}
interface HardwareResp {
  hardware: {
    os: { system: string; release: string; machine: string };
    cpu: { name: string; physical_cores: number; logical_cores: number };
    ram_gb: number;
    ram_available_gb: number;
    disk_free_gb: number;
    gpus: { vendor: string; name: string; vram_mb: number | null; accelerated: boolean }[];
    runtimes: Record<string, string | null>;
  };
  recommendation: { profile: string; reasons: string[]; caveat: string };
  profiles: Record<string, Profile>;
}

export function useHardware() {
  const { api } = useApp();
  const [hw, setHw] = useState<HardwareResp | null>(null);
  useEffect(() => {
    void api?.get<HardwareResp>("/api/system/hardware").then(setHw);
  }, [api]);
  return hw;
}

/** Pull a model through Ollama with live progress. */
export function usePull() {
  const { api, refreshStatus, toast } = useApp();
  const [progress, setProgress] = useState<Record<string, { status: string; pct: number | null }>>({});
  const pull = async (model: string) => {
    if (!api) return false;
    setProgress((p) => ({ ...p, [model]: { status: "starting", pct: null } }));
    try {
      const r = await fetch(`${api.baseUrl}/api/models/pull`, {
        method: "POST",
        headers: { Authorization: `Bearer ${api.token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ model }),
      });
      for await (const ev of readNdjson<{ status?: string; completed?: number; total?: number; error?: string }>(r.body!)) {
        if (ev.error) throw new Error(ev.error);
        const pct = ev.total ? Math.round((100 * (ev.completed ?? 0)) / ev.total) : null;
        setProgress((p) => ({ ...p, [model]: { status: ev.status ?? "", pct } }));
      }
      setProgress((p) => ({ ...p, [model]: { status: "installed", pct: 100 } }));
      await refreshStatus();
      return true;
    } catch (e) {
      toast("error", `Download of ${model} failed: ${(e as Error).message}`);
      setProgress((p) => ({ ...p, [model]: { status: "failed", pct: null } }));
      return false;
    }
  };
  return { progress, pull };
}

export function HardwareCard({ hw }: { hw: HardwareResp }) {
  const h = hw.hardware;
  const gpu = h.gpus.find((g) => g.accelerated) ?? h.gpus[0];
  return (
    <div className="grid grid-cols-2 gap-3 text-sm">
      {[
        [MonitorSmartphone, "System", `${h.os.system} ${h.os.release} (${h.os.machine})`],
        [Cpu, "CPU", `${h.cpu.name} · ${h.cpu.physical_cores ?? "?"} cores / ${h.cpu.logical_cores} threads`],
        [MemoryStick, "Memory", `${h.ram_gb} GB (${h.ram_available_gb} GB free)`],
        [HardDrive, "Disk free", `${h.disk_free_gb} GB`],
        [Gauge, "GPU", gpu ? `${gpu.name}${gpu.vram_mb ? ` · ${(gpu.vram_mb / 1024).toFixed(0)} GB` : ""}${gpu.accelerated ? "" : " (not used for AI)"}` : "None detected (CPU inference)"],
      ].map(([Icon, k, v]) => {
        const I = Icon as typeof Cpu;
        return (
          <div key={k as string} className="flex items-start gap-2 rounded-xl bg-warm p-3">
            <I size={16} className="mt-0.5 shrink-0 text-caramel" />
            <div className="min-w-0">
              <p className="text-xs text-caramel">{k as string}</p>
              <p className="text-bark">{v as string}</p>
            </div>
          </div>
        );
      })}
      <div className="rounded-xl bg-warm p-3">
        <p className="text-xs text-caramel">Runtimes</p>
        <p className="text-xs text-bark">
          {Object.entries(h.runtimes)
            .map(([k, v]) => `${k}: ${v ? v.replace(/^.*?version\s*/i, "").slice(0, 24) : "missing"}`)
            .join(" · ")}
        </p>
      </div>
    </div>
  );
}

export function Setup() {
  const { status, updateSettings, setPage, refreshStatus, api, settings } = useApp();
  const hw = useHardware();
  const { progress, pull } = usePull();
  const [step, setStep] = useState(0);
  const [profile, setProfile] = useState<string | null>(null);
  const [text, setText] = useState<string>("");
  const [vision, setVision] = useState<string>("");
  const [bench, setBench] = useState<{ llm: Record<string, unknown>; asr: Record<string, unknown> } | null>(null);
  const [benching, setBenching] = useState(false);

  useEffect(() => {
    if (hw && !profile) setProfile(hw.recommendation.profile);
  }, [hw, profile]);
  const p = hw && profile ? hw.profiles[profile] : null;
  const installed = useMemo(() => status?.models ?? [], [status?.models]);
  useEffect(() => {
    if (!p) return;
    const names = installed.map((m) => m.name);
    setText((t) => t || (names.includes(p.text_model) ? p.text_model : (installed.find((m) => !m.vision)?.name ?? "")));
    setVision((v) => v || (names.includes(p.vision_model) ? p.vision_model : (installed.find((m) => m.vision)?.name ?? "")));
  }, [p, installed]);

  const steps = ["Welcome", "Your computer", "Local models", "Benchmark"];
  const finish = async () => {
    await updateSettings({
      onboarded: true,
      profile: (profile as "lite" | "balanced" | "performance") ?? "balanced",
      text_model: text || null,
      vision_model: vision || null,
      asr_model: p?.asr_model ?? settings?.asr_model ?? "base",
    });
    setPage("welcome");
  };

  const runBench = async () => {
    if (!api) return;
    setBenching(true);
    try {
      setBench(await api.post("/api/system/benchmark", { text_model: text || null, asr_model: p?.asr_model ?? "base" }));
    } finally {
      setBenching(false);
    }
  };

  return (
    <div className="flex h-full items-start justify-center overflow-y-auto bg-warm px-6 py-10">
      <div className="w-full max-w-3xl">
        <div className="mb-6 flex items-center gap-3">
          <CatMark size={44} mood={benching ? "thinking" : "idle"} />
          <Wordmark />
          <span className="ml-2 text-sm text-caramel">Setup</span>
          <ol className="ml-auto flex gap-1.5">
            {steps.map((s, i) => (
              <li key={s} className={cn("rounded-full px-2.5 py-1 text-xs", i === step ? "bg-bark text-white" : i < step ? "bg-cream text-bark" : "bg-ivory text-caramel")}>
                {i + 1}. {s}
              </li>
            ))}
          </ol>
        </div>

        {step === 0 && (
          <Card className="p-8">
            <h1 className="text-2xl font-semibold text-espresso">Welcome to VEENA</h1>
            <p className="mt-3 text-sm leading-relaxed text-mocha">
              VEENA runs entirely on this computer. Speech recognition, screen understanding, document search and the AI model all run locally, so there is no subscription and no API key. Your
              conversations stay in a local database you can export or delete at any time.
            </p>
            <h2 className="mt-6 text-sm font-semibold text-espresso">What it does cost</h2>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-mocha">
              <li>A one-time download of the models: roughly 1 to 11 GB depending on the profile, over your internet connection.</li>
              <li>Disk space for those models, plus a small database.</li>
              <li>Electricity and battery while the CPU or GPU runs the models. Answers are slower on computers without a supported GPU.</li>
            </ul>
            <Button variant="primary" size="lg" className="mt-8" onClick={() => setStep(1)}>
              Check my computer
            </Button>
          </Card>
        )}

        {step === 1 && (
          <Card className="p-6">
            <h2 className="text-lg font-semibold text-espresso">Your computer</h2>
            {!hw ? (
              <p className="mt-4 text-sm text-caramel">Detecting hardware…</p>
            ) : (
              <>
                <div className="mt-4">
                  <HardwareCard hw={hw} />
                </div>
                <h3 className="mt-6 text-sm font-semibold text-espresso">Choose a profile</h3>
                <p className="text-xs text-caramel">
                  Recommended: {hw.profiles[hw.recommendation.profile].label} ({hw.recommendation.reasons.join("; ")}). {hw.recommendation.caveat}
                </p>
                <div className="mt-3 grid grid-cols-3 gap-3">
                  {Object.entries(hw.profiles).map(([k, pr]) => (
                    <button key={k} type="button" onClick={() => setProfile(k)} className={cn("rounded-xl border-2 p-4 text-left", profile === k ? "border-caramel bg-ivory" : "border-cream bg-white hover:border-sand")}>
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-espresso">{pr.label}</span>
                        {k === hw.recommendation.profile && <Badge tone="strong">Recommended</Badge>}
                      </div>
                      <p className="mt-1 text-xs text-caramel">{pr.target}</p>
                      <p className="mt-2 text-xs text-mocha">{pr.notes}</p>
                      <p className="mt-2 text-xs text-bark">
                        {pr.text_model} · {pr.vision_model} · whisper {pr.asr_model}
                      </p>
                      <p className="mt-1 text-[11px] text-caramel">≈ {pr.download_gb.toFixed(1)} GB download</p>
                    </button>
                  ))}
                </div>
                <div className="mt-6 flex justify-between">
                  <Button variant="ghost" onClick={() => setStep(0)}>
                    Back
                  </Button>
                  <Button variant="primary" onClick={() => setStep(2)}>
                    Continue
                  </Button>
                </div>
              </>
            )}
          </Card>
        )}

        {step === 2 && p && (
          <Card className="p-6">
            <h2 className="text-lg font-semibold text-espresso">Local models</h2>
            {!status?.ollama.running ? (
              <div className="mt-4 rounded-xl border border-ginger bg-cream/50 p-4 text-sm text-bark">
                <p className="font-medium">Ollama is not running.</p>
                <p className="mt-1 text-mocha">
                  VEENA uses Ollama, a free local model runner. Install it from{" "}
                  <button type="button" className="underline" onClick={() => void window.veena?.openExternal("https://ollama.com/download")}>
                    ollama.com/download
                  </button>
                  , start it, then check again.
                </p>
                <Button className="mt-3" onClick={() => void refreshStatus()}>
                  Check again
                </Button>
              </div>
            ) : (
              <>
                <p className="mt-1 text-sm text-mocha">
                  Ollama {status.ollama.version} is running. {installed.length} model(s) installed.
                </p>
                <div className="mt-4 space-y-3">
                  {[
                    ["Text model", p.text_model, "Answers, summaries, coaching"],
                    ["Vision model", p.vision_model, "Screenshot understanding"],
                  ].map(([label, name, why]) => {
                    const have = installed.some((m) => m.name === name);
                    const pr = progress[name];
                    return (
                      <div key={name} className="flex items-center gap-3 rounded-xl border border-cream p-3">
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium text-bark">
                            {label}: {name}
                          </p>
                          <p className="text-xs text-caramel">{why}</p>
                          {pr && !have && (
                            <div className="mt-2">
                              <div className="h-1.5 rounded-full bg-cream">
                                <div className="h-1.5 rounded-full bg-caramel transition-all" style={{ width: `${pr.pct ?? 5}%` }} />
                              </div>
                              <p className="mt-1 text-[11px] text-caramel">
                                {pr.status}
                                {pr.pct != null ? ` · ${pr.pct}%` : ""}
                              </p>
                            </div>
                          )}
                        </div>
                        {have ? (
                          <Badge tone="strong">
                            <Check size={12} /> Installed
                          </Badge>
                        ) : (
                          <Button size="sm" onClick={() => void pull(name)} disabled={!!pr && pr.status !== "failed"}>
                            <Download size={14} /> Download
                          </Button>
                        )}
                      </div>
                    );
                  })}
                </div>
                <div className="mt-5 grid grid-cols-2 gap-3">
                  <label className="text-sm text-bark">
                    Use for text
                    <Select value={text} onChange={(e) => setText(e.target.value)} className="mt-1">
                      <option value="">Choose…</option>
                      {installed.map((m) => (
                        <option key={m.name} value={m.name}>
                          {m.name}
                        </option>
                      ))}
                    </Select>
                  </label>
                  <label className="text-sm text-bark">
                    Use for vision
                    <Select value={vision} onChange={(e) => setVision(e.target.value)} className="mt-1">
                      <option value="">None (OCR text only)</option>
                      {installed
                        .filter((m) => m.vision)
                        .map((m) => (
                          <option key={m.name} value={m.name}>
                            {m.name}
                          </option>
                        ))}
                    </Select>
                  </label>
                </div>
                <p className="mt-2 text-xs text-caramel">Only models that Ollama reports as vision-capable are offered for screen analysis.</p>
              </>
            )}
            <div className="mt-6 flex justify-between">
              <Button variant="ghost" onClick={() => setStep(1)}>
                Back
              </Button>
              <Button variant="primary" onClick={() => setStep(3)} disabled={!text}>
                Continue
              </Button>
            </div>
          </Card>
        )}

        {step === 3 && (
          <Card className="p-6">
            <h2 className="text-lg font-semibold text-espresso">Benchmark this computer</h2>
            <p className="mt-1 text-sm text-mocha">Measures real speed with your chosen models. The speech model downloads on first run (about 75–500 MB).</p>
            <Button className="mt-4" onClick={() => void runBench()} disabled={benching}>
              <Gauge size={15} /> {benching ? "Measuring…" : bench ? "Run again" : "Run benchmark"}
            </Button>
            {bench && (
              <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
                <div className="rounded-xl bg-warm p-3">
                  <p className="text-xs text-caramel">Text model ({String(bench.llm.model ?? "")})</p>
                  {bench.llm.ok ? (
                    <p className="text-bark">
                      {Number(bench.llm.tokens_per_second).toFixed(1)} tokens/s · first token {Math.round(Number(bench.llm.warm_first_token_ms))} ms (warm), {Math.round(Number(bench.llm.cold_first_token_ms))} ms (cold)
                    </p>
                  ) : (
                    <p className="text-bark">{String(bench.llm.error)}</p>
                  )}
                </div>
                <div className="rounded-xl bg-warm p-3">
                  <p className="text-xs text-caramel">Speech (whisper {String(bench.asr.model ?? "")})</p>
                  {bench.asr.ok ? (
                    <p className="text-bark">
                      {Number(bench.asr.real_time_factor).toFixed(2)}× real time ({Math.round(Number(bench.asr.process_ms))} ms for {String(bench.asr.audio_seconds)} s of audio)
                    </p>
                  ) : (
                    <p className="text-bark">{String(bench.asr.error)}</p>
                  )}
                </div>
                <p className="col-span-2 text-xs text-caramel">Real-time factor below 1 means speech is transcribed faster than it is spoken. If it is above 1, choose a smaller speech model in Settings.</p>
              </div>
            )}
            <div className="mt-6 flex justify-between">
              <Button variant="ghost" onClick={() => setStep(2)}>
                Back
              </Button>
              <Button variant="primary" onClick={() => void finish()}>
                Finish setup
              </Button>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
