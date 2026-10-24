# Tested versions

Versions used to build and test this release. Python dependencies are pinned in
`pyproject.toml`; Node dependencies are exact in `apps/desktop/package.json`
and locked in `package-lock.json`.

## Runtimes and tools

| Component | Version | Notes |
|---|---|---|
| Python | 3.12 (dev venv), 3.12 in CI | 3.11+ supported |
| Node.js | v22.22.0 | CI uses Node 22 |
| Electron | 45.0.0 | |
| electron-builder | 26.18.0 | |
| PyInstaller | 6.22.3 | |
| Ollama | 0.40.11 | |
| Tesseract | 5.3.4 | optional |
| espeak-ng, ffmpeg | system packages | tests only (synthetic speech) |

## Models

| Purpose | Model | Size | Source |
|---|---|---|---|
| Text | qwen2.5:1.5b (tests), qwen2.5:3b / 7b (profiles) | 1.0 / 1.9 / 4.7 GB | Ollama library |
| Vision | qwen2.5vl:3b (tested), qwen2.5vl:7b (profile) | 3.2 / 6.0 GB | Ollama library |
| Speech | faster-whisper tiny / base (tested), small+ | 75–500 MB | Hugging Face (Systran) |
| VAD | Silero VAD v6 (ONNX, bundled with faster-whisper) | 2 MB | |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 | 90 MB | Hugging Face |

Vision support is detected from the capabilities Ollama reports for each
installed model, so other vision models (for example gemma3 or llava) also work.

## Python packages

```
ctranslate2               4.8.3
faiss-cpu                 1.15.1
fastapi                   0.162.0
faster-whisper            1.2.1
httpx                     0.28.1
langgraph                 1.2.17
markdown-it-py            4.2.0
numpy                     2.5.4
onnxruntime               1.31.0
pillow                    13.0.0
psutil                    7.2.2
pydantic                  2.14.1
pymupdf                   2.0
pytesseract               0.3.13
pytest                    9.1.1
python-docx               1.2.0
ruff                      0.17.2
sentence-transformers     6.2.0
sqlalchemy                2.1.6
sqlmodel                  0.0.48
torch                     2.14.1+cpu
transformers              5.20.2
uvicorn                   0.54.0
```

## Node packages (direct)

```
@fontsource-variable/inter   5.3.0
class-variance-authority     0.7.1
clsx                         2.1.1
framer-motion                14.6.0
highlight.js                 11.12.0
lucide-react                 1.61.0
mermaid                      12.2.0
react                        19.3.1
react-dom                    19.3.1
react-markdown               10.1.0
recharts                     3.10.1
rehype-highlight             7.0.2
remark-gfm                   4.0.1
tailwind-merge               3.7.0
zustand                      5.0.16
@playwright/test             1.63.0
@tailwindcss/vite            4.3.3
@testing-library/jest-dom    7.0.1
@testing-library/react       16.3.3
@types/node                  26.6.5
@types/react                 19.3.0
@types/react-dom             19.3.0
@vitejs/plugin-react         6.1.2
electron                     45.0.0
electron-builder             26.18.0
eslint                       10.13.0
eslint-plugin-react-hooks    7.1.1
jsdom                        30.1.3
png-to-ico                   3.0.2
sharp                        0.35.5
tailwindcss                  4.3.3
typescript                   6.0.3
typescript-eslint            8.72.0
vite                         8.3.5
vitest                       5.0.5
```

## Platforms

| Platform | Built | Tested |
|---|---|---|
| Linux x64 (Ubuntu 24.04, Xvfb) | AppImage + unpacked, locally and in CI | Full E2E suite against real models locally; packaged-app smoke test with a real model answer |
| Windows x64 | NSIS installer in CI (windows-latest) | Frozen-backend and packaged-app smoke tests in CI (no Ollama on the runner) |
| macOS arm64 | DMG in CI (macos-latest), unsigned | Frozen-backend and packaged-app smoke tests in CI (no Ollama on the runner) |
