# Hardware requirements

| | Minimum | Recommended |
|---|---|---|
| Operating system | Windows 10/11 64-bit; macOS on Apple Silicon; Linux x86_64 (glibc, desktop) | Same |
| Memory (RAM) | 8 GB | 16 GB (Balanced), 32 GB (Performance) |
| Free disk | about 8 GB: app (~1.5 GB installed), AI runtime (up to ~4 GB unpacked on Windows/Linux), one text model (~1 GB) | 15 GB or more for vision and larger models |
| Processor | 64-bit, 4 cores | 8 cores or more |
| Graphics | Not required | A GPU supported by Ollama speeds up answers |
| Internet | Once, for setup downloads | |
| Microphone | Optional (Listen, meetings, practice) | |

Not supported yet: Intel Macs, 32-bit systems, Windows on ARM (the runtime is available, but VEENA's installer is x64 only), ChromeOS and mobile.

## Profiles

| Profile | Text model | Vision model | Speech | Download |
|---|---|---|---|---|
| Lite (8 GB) | qwen2.5:1.5b | qwen3-vl:2b-instruct | whisper tiny | about 3 GB |
| Balanced (16 GB) | qwen3:1.7b | qwen3-vl:2b-instruct | whisper base | about 3.5 GB |
| Performance (32 GB or GPU) | qwen2.5:7b | qwen2.5vl:7b | whisper small | about 11 GB |

Every recommended model is licensed Apache 2.0.

## What to expect (measured, not promised)

Measured on a cloud VM with **4 vCPU, 15.7 GB RAM and no GPU**, the speed of a budget laptop. Your computer may be faster or slower. Source: [`docs/benchmarks/model_eval_run2.json`](benchmarks/model_eval_run2.json).

| Task | qwen2.5:1.5b | qwen3-vl:2b-instruct |
|---|---|---|
| Short answer | about 3 s | |
| Document answer with citation | about 3.4 s | |
| Meeting notes (4 lines) | about 6 s | |
| Interview question and feedback | about 12 s | |
| Screen analysis (one screenshot) | | 33–40 s |

The first answer after starting VEENA also loads the model, which adds seconds to a minute. A GPU or Apple Silicon is typically much faster, but this was **not measured**.

VEENA does not promise real-time help on slow hardware. The Setup benchmark measures your own computer.
