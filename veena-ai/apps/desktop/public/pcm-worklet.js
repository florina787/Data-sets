// AudioWorklet: collects mono float samples (the AudioContext runs at 16 kHz)
// and posts fixed 1024-sample frames plus a level meter value to the main thread.
class PcmCapture extends AudioWorkletProcessor {
  constructor() {
    super();
    this.frame = new Float32Array(1024);
    this.n = 0;
  }

  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    for (let i = 0; i < ch.length; i++) {
      this.frame[this.n++] = ch[i];
      if (this.n === this.frame.length) {
        let sum = 0;
        for (let j = 0; j < this.frame.length; j++) sum += this.frame[j] * this.frame[j];
        const out = this.frame.slice();
        this.port.postMessage({ pcm: out, rms: Math.sqrt(sum / this.frame.length) }, [out.buffer]);
        this.n = 0;
      }
    }
    return true;
  }
}

registerProcessor("pcm-capture", PcmCapture);
