import { AlertTriangle, Check, Cpu, Download, Gauge, HardDrive, Lock, MemoryStick, Mic, MonitorSmartphone, RotateCcw, ShieldCheck, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { CatMark, Wordmark } from "../components/CatMark";
import { Badge, Button, Card, cn, Select, Switch } from "../components/ui";
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
  catalog: Record<string, CatalogEntry>;
}
interface CatalogEntry {
  kind: string;
  bytes: number;
  license: string;
  commercial: boolean;
  card: string;
}
interface RuntimeStatus {
  running: boolean;
  version: string | null;
  system_binary: string | null;
  managed_binary: string | null;
  installing: boolean;
  supported: boolean;
  platform: string;
  download: { version: string; file: string | null; bytes: number | null; required_free_bytes: number; free_bytes: number; license: string; source: string };
}

export function useHardware() {
  const { api } = useApp();
  const [hw, setHw] = useState<HardwareResp | null>(null);
  useEffect(() => {
    void api?.get<HardwareResp>("/api/system/hardware").then(setHw);
  }, [api]);
  return hw;
}

/** Pull a model through Ollama with live progress. Ollama checks every layer's
 * digest and resumes partial downloads, so Retry continues where it stopped. */
export function usePull() {
  const { api, refreshStatus, toast } = useApp();
  const [progress, setProgress] = useState<Record<string, { status: string; pct: number | null }>>({});
  const aborts = useRef<Record<string, AbortController>>({});
  const pull = async (model: string) => {
    if (!api) return false;
    const ctl = new AbortController();
    aborts.current[model] = ctl;
    setProgress((p) => ({ ...p, [model]: { status: "starting", pct: null } }));
    try {
      const r = await fetch(`${api.baseUrl}/api/models/pull`, {
        method: "POST",
        headers: { Authorization: `Bearer ${api.token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ model }),
        signal: ctl.signal,
      });
      if (!r.ok) throw new Error(((await r.json().catch(() => ({}))) as { detail?: string }).detail ?? `HTTP ${r.status}`);
      for await (const ev of readNdjson<{ status?: string; completed?: number; total?: number; error?: string }>(r.body!)) {
        if (ev.error) throw new Error(ev.error);
        const pct = ev.total ? Math.round((100 * (ev.completed ?? 0)) / ev.total) : null;
        setProgress((p) => ({ ...p, [model]: { status: ev.status ?? "", pct } }));
      }
      setProgress((p) => ({ ...p, [model]: { status: "installed", pct: 100 } }));
      await refreshStatus();
      return true;
    } catch (e) {
      const cancelled = ctl.signal.aborted;
      if (!cancelled) toast("error", `Download of ${model} failed: ${(e as Error).message}`);
      setProgress((p) => ({ ...p, [model]: { status: cancelled ? "cancelled" : "failed", pct: null } }));
      return false;
    } finally {
      delete aborts.current[model];
    }
  };
  const cancel = (model: string) => aborts.current[model]?.abort();
  return { progress, pull, cancel };
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

const gb = (b: number | null | undefined) => (b ? `${(b / 1e9).toFixed(1)} GB` : "unknown size");
const STEPS = ["Welcome", "Your computer", "AI runtime", "Models", "Privacy", "Permissions", "First answer"];
const MIN_RAM_GB = 8;

function Progress({ pct, label }: { pct: number | null; label: string }) {
  return (
    <div className="mt-3">
      <div className="h-2 rounded-full bg-cream" role="progressbar" aria-valuenow={pct ?? undefined} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
        <div className="h-2 rounded-full bg-caramel transition-all" style={{ width: `${pct ?? 4}%` }} />
      </div>
      <p className="mt-1 text-xs text-caramel">
        {label}
        {pct != null ? ` · ${pct}%` : ""}
      </p>
    </div>
  );
}

function Nav({ back, next, nextLabel = "Continue", nextDisabled }: { back?: () => void; next: () => void; nextLabel?: string; nextDisabled?: boolean }) {
  return (
    <div className="mt-6 flex justify-between">
      {back ? (
        <Button variant="ghost" onClick={back}>
          Back
        </Button>
      ) : (
        <span />
      )}
      <Button variant="primary" onClick={next} disabled={nextDisabled}>
        {nextLabel}
      </Button>
    </div>
  );
}

/** The local AI runtime: reuse a running or installed Ollama, or download the pinned release with consent. */
function RuntimeStep({ onReady }: { onReady: (ok: boolean) => void }) {
  const { api, refreshStatus } = useApp();
  const [rt, setRt] = useState<RuntimeStatus | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [pct, setPct] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = async () => {
    if (!api) return;
    const s = await api.get<RuntimeStatus>("/api/runtime");
    setRt(s);
    onReady(s.running);
  };
  useEffect(() => {
    void load();
  }, [api]); // eslint-disable-line react-hooks/exhaustive-deps

  const start = async () => {
    if (!api) return;
    setBusy("Starting the AI runtime…");
    setError(null);
    try {
      await api.post("/api/runtime/start", {});
      await refreshStatus();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
      await load();
    }
  };

  const install = async () => {
    if (!api) return;
    setError(null);
    setBusy("Downloading");
    setPct(0);
    try {
      const r = await fetch(`${api.baseUrl}/api/runtime/install`, { method: "POST", headers: { Authorization: `Bearer ${api.token}` } });
      for await (const ev of readNdjson<{ status?: string; completed?: number; total?: number; error?: string }>(r.body!)) {
        if (ev.error) throw new Error(ev.error);
        if (ev.status === "downloading" && ev.total) {
          setPct(Math.round((100 * (ev.completed ?? 0)) / ev.total));
          setBusy(`Downloading ${gb(ev.completed)} of ${gb(ev.total)}`);
        } else if (ev.status === "verifying") setBusy("Checking the download's integrity (SHA-256)…");
        else if (ev.status === "extracting") setBusy("Unpacking…");
        else if (ev.status === "starting") setBusy("Starting the AI runtime…");
      }
      await refreshStatus();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
      setPct(null);
      await load();
    }
  };

  if (!rt) return <p className="mt-4 text-sm text-caramel">Checking for a local AI runtime…</p>;
  if (rt.running)
    return (
      <div className="mt-4 flex items-start gap-3 rounded-xl bg-warm p-4 text-sm">
        <ShieldCheck size={18} className="mt-0.5 shrink-0 text-caramel" />
        <div>
          <p className="font-medium text-bark">Local AI runtime (Ollama {rt.version}) is running.</p>
          <p className="mt-1 text-xs text-caramel">It answers only on this computer (127.0.0.1). Nothing is sent to a cloud AI service.</p>
        </div>
      </div>
    );
  const installed = rt.system_binary || rt.managed_binary;
  const lowDisk = rt.download.free_bytes < rt.download.required_free_bytes;
  return (
    <div className="mt-4 rounded-xl border border-cream p-4 text-sm">
      {installed ? (
        <>
          <p className="font-medium text-bark">The AI runtime is installed but not running.</p>
          <Button className="mt-3" variant="primary" onClick={() => void start()} disabled={!!busy}>
            Start the AI runtime
          </Button>
        </>
      ) : !rt.supported ? (
        <p className="text-bark">VEENA cannot set up the AI runtime automatically on this system ({rt.platform}). Install Ollama from ollama.com, then press Check again.</p>
      ) : (
        <>
          <p className="font-medium text-bark">VEENA needs a free local AI runtime.</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-mocha">
            <li>
              It is Ollama {rt.download.version} ({rt.download.license} licence), downloaded once from its official release: {gb(rt.download.bytes)}.
            </li>
            <li>The file is checked against the SHA-256 checksum published with that release before anything runs.</li>
            <li>It is installed for your account only, inside VEENA's own folder. No administrator rights are needed.</li>
          </ul>
          <p className={cn("mt-2 text-xs", lowDisk ? "font-semibold text-bark" : "text-caramel")}>
            Needs about {gb(rt.download.required_free_bytes)} free while installing · {gb(rt.download.free_bytes)} free now
            {lowDisk ? ". Free up space, then press Retry." : ""}
          </p>
          {busy ? (
            <>
              <Progress pct={pct} label={busy} />
              <Button className="mt-3" variant="ghost" size="sm" onClick={() => void api?.post("/api/runtime/cancel", {})}>
                <X size={14} /> Cancel download
              </Button>
            </>
          ) : (
            <Button className="mt-3" variant="primary" onClick={() => void install()} disabled={lowDisk}>
              <Download size={15} /> Download and set up ({gb(rt.download.bytes)})
            </Button>
          )}
        </>
      )}
      {error && (
        <div className="mt-3 flex items-start gap-2 rounded-lg bg-ivory p-3 text-bark" role="alert">
          <AlertTriangle size={15} className="mt-0.5 shrink-0" />
          <span className="flex-1">{error}</span>
          <Button size="sm" onClick={() => void (installed ? start() : install())}>
            <RotateCcw size={13} /> Retry
          </Button>
        </div>
      )}
      <Button className="mt-3" variant="ghost" size="sm" onClick={() => void load()}>
        Check again
      </Button>
    </div>
  );
}

function PermissionsStep() {
  const [mic, setMic] = useState<"unknown" | "granted" | "denied" | "none">("unknown");
  const testMic = async () => {
    try {
      const os = await window.veena?.mediaAccess("microphone");
      if (os && os !== "granted") return setMic("denied");
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((t) => t.stop()); // test only: nothing is recorded
      setMic("granted");
    } catch (e) {
      setMic((e as Error).name === "NotFoundError" ? "none" : "denied");
    }
  };
  const mac = navigator.userAgent.includes("Mac");
  return (
    <div className="mt-4 space-y-3 text-sm">
      <div className="rounded-xl border border-cream p-4">
        <p className="flex items-center gap-2 font-medium text-bark">
          <Mic size={15} /> Microphone <span className="text-xs font-normal text-caramel">(for Listen, meetings and interview practice)</span>
        </p>
        <p className="mt-1 text-mocha">VEENA only listens after you press Listen, and shows a recording indicator while it does. Audio is transcribed on this computer and never saved as a recording.</p>
        <Button className="mt-3" size="sm" onClick={() => void testMic()}>
          Allow and test the microphone
        </Button>
        {mic === "granted" && (
          <p className="mt-2 flex items-center gap-1.5 text-bark">
            <Check size={14} /> Microphone access works.
          </p>
        )}
        {mic === "denied" && (
          <p className="mt-2 text-bark" role="alert">
            Access was blocked. Turn it on in {mac ? "System Settings → Privacy & Security → Microphone" : "Windows Settings → Privacy & security → Microphone"} and try again. You can also skip this
            and type instead.
          </p>
        )}
        {mic === "none" && <p className="mt-2 text-bark">No microphone was found. You can still type questions.</p>}
      </div>
      <div className="rounded-xl border border-cream p-4">
        <p className="flex items-center gap-2 font-medium text-bark">
          <MonitorSmartphone size={15} /> Screen <span className="text-xs font-normal text-caramel">(for Screen Intelligence)</span>
        </p>
        <p className="mt-1 text-mocha">
          Nothing is captured until you pick a screen or window in VEENA's own picker, and a Sharing pill with a Stop button stays visible while it is shared.
          {mac ? " macOS asks for Screen Recording permission the first time; allow VEENA in System Settings → Privacy & Security → Screen Recording." : ""}
        </p>
      </div>
      <p className="text-xs text-caramel">Both are optional. You can change them later in your system settings.</p>
    </div>
  );
}

/** A real answer from the chosen model. "VEENA is ready." appears only after it succeeds. */
function FirstAnswerStep({ model, onResult }: { model: string; onResult: (ok: boolean) => void }) {
  const { api } = useApp();
  const [state, setState] = useState<{ phase: "asking" | "ok" | "failed"; answer?: string; ms?: number; error?: string }>({ phase: "asking" });
  const ask = async () => {
    if (!api) return;
    setState({ phase: "asking" });
    try {
      const r = await api.post<{ ok: boolean; answer?: string; ms?: number; error?: string }>("/api/system/healthcheck", { model });
      setState(r.ok ? { phase: "ok", answer: r.answer, ms: r.ms } : { phase: "failed", error: r.error ?? "The model returned an empty answer." });
      onResult(r.ok);
    } catch (e) {
      setState({ phase: "failed", error: (e as Error).message });
      onResult(false);
    }
  };
  useEffect(() => {
    void ask();
  }, [model]); // eslint-disable-line react-hooks/exhaustive-deps
  if (state.phase === "asking")
    return (
      <div className="mt-6 flex items-center gap-4">
        <CatMark size={56} mood="thinking" />
        <p className="text-sm text-mocha">Asking {model} a first question on this computer. The first answer loads the model and can take a minute on a laptop CPU.</p>
      </div>
    );
  if (state.phase === "failed")
    return (
      <div className="mt-6 rounded-xl bg-ivory p-4 text-sm text-bark" role="alert">
        <p className="font-medium">The model did not answer.</p>
        <p className="mt-1 text-mocha">{state.error}</p>
        <Button className="mt-3" size="sm" onClick={() => void ask()}>
          <RotateCcw size={13} /> Try again
        </Button>
      </div>
    );
  return (
    <div className="mt-6 flex items-center gap-4">
      <CatMark size={64} />
      <div>
        <p className="text-2xl font-semibold text-espresso">VEENA is ready.</p>
        <p className="mt-1 text-sm text-mocha">
          {model} answered “{state.answer}” in {((state.ms ?? 0) / 1000).toFixed(1)} s, entirely on this computer.
        </p>
      </div>
    </div>
  );
}

export function Setup() {
  const { status, updateSettings, setPage, api, settings } = useApp();
  const hw = useHardware();
  const { progress, pull, cancel } = usePull();
  const [step, setStepRaw] = useState(() => Math.min(settings?.setup_step ?? 0, STEPS.length - 1));
  const [profile, setProfile] = useState<string | null>(null);
  const [text, setText] = useState<string>("");
  const [vision, setVision] = useState<string>("");
  const [runtimeOk, setRuntimeOk] = useState(false);
  const [ready, setReady] = useState(false);
  const [checkUpdates, setCheckUpdates] = useState(settings?.check_updates ?? true);
  const [bench, setBench] = useState<{ llm: Record<string, unknown>; asr: Record<string, unknown> } | null>(null);
  const [benching, setBenching] = useState(false);

  // Progress is saved so Setup resumes at the same step after a restart.
  const setStep = (n: number) => {
    setStepRaw(n);
    void updateSettings({ setup_step: n });
  };

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
  // Profile, models and selections need the hardware data; go back to it if a resumed step lacks it.
  useEffect(() => {
    if (step >= 3 && hw && !p) setStepRaw(1);
  }, [step, hw, p]);

  const lic = (name: string) => hw?.catalog[name] ?? hw?.catalog[name.replace(/:latest$/, "")];
  const finish = async () => {
    await updateSettings({
      onboarded: true,
      setup_step: 0,
      check_updates: checkUpdates,
      profile: (profile as "lite" | "balanced" | "performance") ?? "balanced",
      text_model: text || null,
      vision_model: vision || null,
      asr_model: p?.asr_model ?? settings?.asr_model ?? "base",
      // Used only when speech-language auto-detection is unsure (short phrases).
      asr_fallback_language: (navigator.language || "en").slice(0, 2).toLowerCase(),
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

  const lowRam = hw ? hw.hardware.ram_gb < MIN_RAM_GB - 0.5 : false;

  return (
    <div className="flex h-full items-start justify-center overflow-y-auto bg-warm px-6 py-10">
      <div className="w-full max-w-3xl">
        <div className="mb-6 flex flex-wrap items-center gap-3">
          <CatMark size={44} mood={benching ? "thinking" : "idle"} />
          <Wordmark />
          <span className="ml-2 text-sm text-caramel">Setup</span>
          <ol className="ml-auto flex flex-wrap gap-1.5" aria-label="Setup progress">
            {STEPS.map((s, i) => (
              <li key={s} aria-current={i === step ? "step" : undefined} className={cn("rounded-full px-2.5 py-1 text-xs", i === step ? "bg-bark text-white" : i < step ? "bg-cream text-bark" : "bg-ivory text-caramel")}>
                {i + 1}. {s}
              </li>
            ))}
          </ol>
        </div>

        {step === 0 && (
          <Card className="p-8">
            <h1 className="text-2xl font-semibold text-espresso">Welcome to VEENA</h1>
            <p className="mt-3 text-sm leading-relaxed text-mocha">
              VEENA runs entirely on this computer. Speech recognition, screen understanding, document search and the AI model all run locally, so there is no subscription, no account and no API key.
              Your conversations stay in a local database you can export or delete at any time.
            </p>
            <h2 className="mt-6 text-sm font-semibold text-espresso">What setup will do</h2>
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-mocha">
              <li>Check that this computer can run VEENA.</li>
              <li>Set up the free local AI runtime, if it is not already installed (one download, with your permission).</li>
              <li>Download an AI model: roughly 1 to 4 GB depending on the profile.</li>
              <li>Ask the model a first question to confirm everything works.</li>
            </ul>
            <p className="mt-4 text-xs text-caramel">It takes about 5 to 20 minutes, mostly downloading. You can close VEENA and it will resume here.</p>
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
                <p className="mt-3 text-xs text-caramel">Minimum: {MIN_RAM_GB} GB memory and about 8 GB free disk. Recommended: 16 GB memory. A supported GPU makes answers faster but is not required.</p>
                {lowRam && (
                  <p className="mt-2 flex items-start gap-2 rounded-lg bg-ivory p-3 text-sm text-bark" role="alert">
                    <AlertTriangle size={15} className="mt-0.5 shrink-0" /> This computer has less memory than VEENA needs. The Lite profile will work but answers will be slow, and screen analysis may not
                    fit in memory.
                  </p>
                )}
                <h3 className="mt-6 text-sm font-semibold text-espresso">Choose a profile</h3>
                <p className="text-xs text-caramel">
                  Recommended: {hw.profiles[hw.recommendation.profile].label} ({hw.recommendation.reasons.join("; ")}). {hw.recommendation.caveat}
                </p>
                <div className="mt-3 grid gap-3 sm:grid-cols-3">
                  {Object.entries(hw.profiles).map(([k, pr]) => (
                    <button key={k} type="button" onClick={() => setProfile(k)} aria-pressed={profile === k} className={cn("rounded-xl border-2 p-4 text-left", profile === k ? "border-caramel bg-ivory" : "border-cream bg-white hover:border-sand")}>
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
                <Nav back={() => setStep(0)} next={() => setStep(2)} />
              </>
            )}
          </Card>
        )}

        {step === 2 && (
          <Card className="p-6">
            <h2 className="text-lg font-semibold text-espresso">AI runtime</h2>
            <p className="mt-1 text-sm text-mocha">VEENA runs AI models with Ollama, a free, open-source local runtime.</p>
            <RuntimeStep onReady={setRuntimeOk} />
            <Nav back={() => setStep(1)} next={() => setStep(3)} nextDisabled={!runtimeOk} />
          </Card>
        )}

        {step === 3 && p && (
          <Card className="p-6">
            <h2 className="text-lg font-semibold text-espresso">Models</h2>
            <p className="mt-1 text-sm text-mocha">
              {status?.ollama.running ? `${installed.length} model(s) installed.` : "The AI runtime is not running. Go back one step to start it."} Downloads resume if interrupted and are
              checked by the runtime before use.
            </p>
            <div className="mt-4 space-y-3">
              {(
                [
                  ["Text model", p.text_model, "Answers, summaries, coaching"],
                  ["Vision model", p.vision_model, "Screenshot understanding (optional)"],
                ] as const
              ).map(([label, name, why]) => {
                const have = installed.some((m) => m.name === name);
                const pr = progress[name];
                const c = lic(name);
                const busy = !!pr && !["failed", "cancelled", "installed"].includes(pr.status);
                return (
                  <div key={name} className="flex items-center gap-3 rounded-xl border border-cream p-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-bark">
                        {label}: {name}
                      </p>
                      <p className="text-xs text-caramel">
                        {why} · {gb(c?.bytes)} · {c ? `${c.license} licence` : "licence not in VEENA's catalogue"}
                      </p>
                      {pr && !have && <Progress pct={pr.pct} label={pr.status} />}
                    </div>
                    {have ? (
                      <Badge tone="strong">
                        <Check size={12} /> Installed
                      </Badge>
                    ) : busy ? (
                      <Button size="sm" variant="ghost" onClick={() => cancel(name)}>
                        <X size={14} /> Cancel
                      </Button>
                    ) : (
                      <Button size="sm" onClick={() => void pull(name)} disabled={!status?.ollama.running}>
                        {pr?.status === "failed" || pr?.status === "cancelled" ? <RotateCcw size={14} /> : <Download size={14} />} {pr?.status === "failed" || pr?.status === "cancelled" ? "Retry" : "Download"}
                      </Button>
                    )}
                  </div>
                );
              })}
            </div>
            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              <label className="text-sm text-bark">
                Use for text
                <Select value={text} onChange={(e) => setText(e.target.value)} className="mt-1">
                  <option value="">Choose…</option>
                  {installed.map((m) => (
                    <option key={m.name} value={m.name}>
                      {m.name}
                      {lic(m.name)?.commercial === false ? " (non-commercial licence)" : ""}
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
                        {lic(m.name)?.commercial === false ? " (non-commercial licence)" : ""}
                      </option>
                    ))}
                </Select>
              </label>
            </div>
            {[text, vision].some((m) => m && lic(m)?.commercial === false) && (
              <p className="mt-2 text-xs text-bark" role="note">
                A selected model's licence allows research and evaluation only, not commercial use. VEENA's recommended models are Apache-2.0.
              </p>
            )}
            <p className="mt-2 text-xs text-caramel">Only models that the runtime reports as vision-capable are offered for screen analysis.</p>
            <Nav back={() => setStep(2)} next={() => setStep(4)} nextDisabled={!text} />
          </Card>
        )}

        {step === 4 && (
          <Card className="p-6">
            <h2 className="text-lg font-semibold text-espresso">Your data stays here</h2>
            <ul className="mt-3 space-y-2 text-sm text-mocha">
              {[
                "Conversations, transcripts and documents are stored in a database on this computer.",
                "AI answers are generated on this computer. VEENA does not call cloud AI services.",
                "Raw audio and screenshots are never saved. Screenshots have detected secrets masked before analysis.",
                "History older than 30 days is deleted automatically. Change this, export, or delete everything in Settings.",
                "Internet is used only to download the runtime and models, and (if you allow it below) to check for updates.",
              ].map((t) => (
                <li key={t} className="flex items-start gap-2">
                  <Lock size={14} className="mt-0.5 shrink-0 text-caramel" /> {t}
                </li>
              ))}
            </ul>
            <div className="mt-5 rounded-xl border border-cream p-4">
              <Switch
                checked={checkUpdates}
                onChange={setCheckUpdates}
                label="Check for VEENA updates"
                description="Once a day VEENA asks GitHub for the latest version number. No personal data or usage is sent. Updates are never installed without you."
              />
            </div>
            <Nav back={() => setStep(3)} next={() => setStep(5)} />
          </Card>
        )}

        {step === 5 && (
          <Card className="p-6">
            <h2 className="text-lg font-semibold text-espresso">Permissions</h2>
            <PermissionsStep />
            <Nav back={() => setStep(4)} next={() => setStep(6)} />
          </Card>
        )}

        {step === 6 && (
          <Card className="p-6">
            <h2 className="text-lg font-semibold text-espresso">First answer</h2>
            {text ? <FirstAnswerStep model={text} onResult={setReady} /> : <p className="mt-4 text-sm text-bark">Choose a text model first.</p>}
            <div className="mt-6 border-t border-cream pt-4">
              <p className="text-sm text-mocha">Optional: measure this computer's speed with your chosen models.</p>
              <Button className="mt-2" size="sm" onClick={() => void runBench()} disabled={benching || !ready}>
                <Gauge size={15} /> {benching ? "Measuring…" : bench ? "Run again" : "Run benchmark"}
              </Button>
              {bench && (
                <div className="mt-3 grid gap-3 text-sm sm:grid-cols-2">
                  <div className="rounded-xl bg-warm p-3">
                    <p className="text-xs text-caramel">Text model ({String(bench.llm.model ?? "")})</p>
                    {bench.llm.ok ? (
                      <p className="text-bark">
                        {Number(bench.llm.tokens_per_second).toFixed(1)} tokens/s · first token {Math.round(Number(bench.llm.warm_first_token_ms))} ms (warm), {Math.round(Number(bench.llm.cold_first_token_ms))}{" "}
                        ms (cold)
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
                </div>
              )}
            </div>
            <Nav back={() => setStep(5)} next={() => void finish()} nextLabel="Finish setup" nextDisabled={!ready} />
          </Card>
        )}
      </div>
    </div>
  );
}
