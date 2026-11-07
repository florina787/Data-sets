# Build environment (as actually used)

* Cloud container, Linux x86_64, 4 CPU threads, 15 GB RAM, no GPU. Python 3.13.
* No Qwen runtime was installed and the existing copilots had no Qwen adapter.
* Ollama: `ollama.com/download` redirects to GitHub releases, which the container's network policy blocked (403/404).
* Used instead: `llama-cpp-python[server]` 0.3.36 (built from source) serving
  `Qwen/Qwen2.5-Coder-3B-Instruct-GGUF` → `qwen2.5-coder-3b-instruct-q4_k_m.gguf` (2.1 GB, from Hugging Face) at
  `http://127.0.0.1:11434/v1` with alias `qwen2.5-coder:3b` — the same URL and model name Ollama would use, so the
  `.env.example` defaults work for both.
* Measured on this hardware: short generation ~0.5 s; general chat 4–16 s; text-to-SQL 7–43 s per question.
* Model weights are not committed (`*.gguf` in `.gitignore`).
