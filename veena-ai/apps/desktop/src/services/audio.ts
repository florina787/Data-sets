// Microphone / system-audio capture -> 16 kHz PCM frames -> backend WebSocket.
//
// Recovery behaviour:
//  * If the selected input device disappears (unplugged), capture falls back to
//    the system default device and reports it.
//  * If the WebSocket drops while recording, it reconnects with backoff and
//    capture continues; frames produced while disconnected are dropped (the
//    UI shows it), never buffered without limit.

export type AudioSource = "mic" | "system";

export interface AudioEvent {
  type: string;
  [k: string]: unknown;
}

export interface AudioCallbacks {
  onEvent: (ev: AudioEvent) => void;
  onLevel: (rms: number) => void;
  onState: (state: CaptureState, detail?: string) => void;
}

export type CaptureState = "connecting" | "loading_model" | "listening" | "paused" | "reconnecting" | "stopped" | "error";

const HEADER_BYTES = 8;

export function encodeFrame(tsMs: number, pcm: Float32Array): ArrayBuffer {
  const buf = new ArrayBuffer(HEADER_BYTES + pcm.length * 2);
  const view = new DataView(buf);
  view.setFloat64(0, tsMs, true);
  for (let i = 0; i < pcm.length; i++) {
    const s = Math.max(-1, Math.min(1, pcm[i]));
    view.setInt16(HEADER_BYTES + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return buf;
}

export async function listInputDevices(): Promise<MediaDeviceInfo[]> {
  const all = await navigator.mediaDevices.enumerateDevices();
  return all.filter((d) => d.kind === "audioinput");
}

export class AudioCapture {
  private ctx: AudioContext | null = null;
  private node: AudioWorkletNode | null = null;
  private stream: MediaStream | null = null;
  private ws: WebSocket | null = null;
  private stopped = false;
  private paused = false;
  private retries = 0;
  droppedWhileOffline = 0;

  constructor(
    private wsBase: string,
    private token: string,
    private sessionId: string,
    private source: AudioSource,
    private cb: AudioCallbacks,
    private deviceId?: string,
    private externalStream?: MediaStream,
  ) {}

  async start(): Promise<void> {
    this.stopped = false;
    this.cb.onState("connecting");
    await this.openStream();
    this.connect();
    navigator.mediaDevices.addEventListener("devicechange", this.onDeviceChange);
  }

  private async openStream(): Promise<void> {
    if (this.externalStream) {
      // System audio arrives on the screen-share stream (Windows loopback).
      const track = this.externalStream.getAudioTracks()[0];
      if (!track) throw new Error("The shared source has no audio track. System audio needs Windows.");
      this.stream = new MediaStream([track]);
    } else {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          deviceId: this.deviceId ? { exact: this.deviceId } : undefined,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
    }
    const track = this.stream.getAudioTracks()[0];
    track.addEventListener("ended", this.onTrackEnded);
    this.ctx = new AudioContext({ sampleRate: 16000 });
    await this.ctx.audioWorklet.addModule(new URL("pcm-worklet.js", document.baseURI).href);
    const src = this.ctx.createMediaStreamSource(this.stream);
    this.node = new AudioWorkletNode(this.ctx, "pcm-capture");
    this.node.port.onmessage = (e: MessageEvent<{ pcm: Float32Array; rms: number }>) => {
      this.cb.onLevel(this.paused ? 0 : e.data.rms);
      if (this.paused) return;
      if (this.ws?.readyState === WebSocket.OPEN) {
        // Backpressure on the socket: if the OS send buffer is backing up,
        // drop this frame instead of queueing unbounded memory.
        if (this.ws.bufferedAmount > 256 * 1024) {
          this.droppedWhileOffline++;
          return;
        }
        this.ws.send(encodeFrame(Date.now(), e.data.pcm));
      } else {
        this.droppedWhileOffline++;
      }
    };
    src.connect(this.node);
  }

  private connect() {
    const url = `${this.wsBase}/ws/audio?session_id=${encodeURIComponent(this.sessionId)}&source=${this.source}`;
    const ws = new WebSocket(url, ["veena", this.token]);
    ws.binaryType = "arraybuffer";
    this.ws = ws;
    ws.onmessage = (m) => {
      const ev = JSON.parse(String(m.data)) as AudioEvent;
      if (ev.type === "status") {
        const st = ev.state as string;
        if (st === "ready" || st === "listening") {
          this.retries = 0;
          this.cb.onState(this.paused ? "paused" : "listening");
        } else if (st === "loading_model") this.cb.onState("loading_model", String(ev.model ?? ""));
        else if (st === "paused") this.cb.onState("paused");
      }
      this.cb.onEvent(ev);
    };
    ws.onclose = (e) => {
      if (this.stopped) return;
      if (e.code === 4401 || e.code === 4403 || e.code === 4400) {
        this.cb.onState("error", "The backend refused the audio connection.");
        void this.stop();
        return;
      }
      if (this.retries >= 6) {
        this.cb.onState("error", "Lost connection to the transcription service.");
        void this.stop();
        return;
      }
      this.retries++;
      this.cb.onState("reconnecting");
      setTimeout(() => !this.stopped && this.connect(), 500 * 2 ** (this.retries - 1));
    };
  }

  private onTrackEnded = async () => {
    if (this.stopped) return;
    if (this.externalStream) {
      this.cb.onState("error", "System audio stopped because screen sharing ended.");
      await this.stop();
      return;
    }
    // Device unplugged or permission revoked: try the default device.
    this.cb.onState("reconnecting", "Microphone disconnected; switching to the default device.");
    this.teardownAudio();
    this.deviceId = undefined;
    try {
      await new Promise((r) => setTimeout(r, 600));
      await this.openStream();
      this.cb.onState(this.paused ? "paused" : "listening", "Switched to the default microphone.");
    } catch (e) {
      this.cb.onState("error", `Microphone unavailable: ${e instanceof Error ? e.message : String(e)}`);
      await this.stop();
    }
  };

  private onDeviceChange = async () => {
    if (!this.deviceId || this.externalStream) return;
    const devices = await listInputDevices();
    if (!devices.some((d) => d.deviceId === this.deviceId)) await this.onTrackEnded();
  };

  pause() {
    this.paused = true;
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify({ type: "pause" }));
    this.cb.onState("paused");
  }

  resume() {
    this.paused = false;
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify({ type: "resume" }));
    this.cb.onState("listening");
  }

  private teardownAudio() {
    this.node?.disconnect();
    this.node = null;
    if (!this.externalStream) this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    void this.ctx?.close();
    this.ctx = null;
  }

  async stop(): Promise<void> {
    if (this.stopped) return;
    this.stopped = true;
    navigator.mediaDevices.removeEventListener("devicechange", this.onDeviceChange);
    this.teardownAudio();
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      // Let the backend flush the open utterance before closing.
      this.ws.send(JSON.stringify({ type: "stop" }));
      const ws = this.ws;
      setTimeout(() => ws.close(), 8000);
    }
    this.cb.onState("stopped");
  }
}
