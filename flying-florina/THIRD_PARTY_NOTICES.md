# Third-party notices

Flying_Florina is distributed under the GNU GPL v3 (see `LICENSE`, identical to the repository root license).
It uses only open-source dependencies, all under permissive licenses compatible with GPL-3.0. Nothing is
fetched at runtime; packages are installed once during setup. No model weights are bundled or downloaded.

Licenses were read from installed package metadata on 2026-10-25 (`importlib.metadata` / `package.json`).
Re-check before redistribution.

## Python (backend/.venv, including transitive dependencies)

| Package | Version | License |
|---|---|---|
| annotated-doc | 0.0.5 | MIT |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.15.1 | MIT |
| attrs | 26.1.0 | MIT |
| certifi | 2026.10.23 | MPL-2.0 |
| cffi | 2.1.1 | MIT-0 |
| charset-normalizer | 3.5.2 | MIT |
| click | 8.5.0 | BSD-3-Clause |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause |
| fastapi | 0.162.0 | MIT |
| h11 | 0.16.0 | MIT |
| httpcore | 1.0.9 | BSD-3-Clause |
| httpcore2 | 2.16.0 | BSD-3-Clause |
| httpx | 0.28.1 | BSD-3-Clause |
| httpx2 | 2.16.0 | BSD-3-Clause |
| idna | 3.20 | BSD-3-Clause |
| iniconfig | 2.3.1 | MIT |
| jsonschema | 4.26.0 | MIT |
| jsonschema-specifications | 2025.9.1 | MIT |
| mcp | 2.3.0 | MIT |
| mcp-types | 2.3.0 | MIT |
| opentelemetry-api | 1.45.1 | Apache-2.0 |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| pillow | 13.0.0 | MIT-CMU |
| pip | 26.2.2 | MIT |
| pluggy | 1.7.0 | MIT |
| pycparser | 3.12 | BSD-3-Clause |
| pydantic | 2.13.5 | MIT |
| pydantic_core | 2.46.5 | MIT |
| Pygments | 2.21.0 | BSD-2-Clause |
| PyJWT | 2.15.1 | MIT |
| pytest | 9.1.1 | MIT |
| python-multipart | 0.0.32 | Apache-2.0 |
| PyYAML | 6.0.3 | MIT |
| referencing | 0.37.0 | MIT |
| reportlab | 5.0.1 | BSD License |
| rpds-py | 2026.9.1 | MIT |
| ruff | 0.17.2 | MIT |
| sse-starlette | 3.5.1 | BSD-3-Clause |
| starlette | 1.10.0 | BSD-3-Clause |
| truststore | 0.10.5 | MIT |
| typing-inspection | 0.4.4 | MIT |
| typing_extensions | 4.16.0 | PSF-2.0 |
| uvicorn | 0.54.0 | BSD-3-Clause |

## JavaScript (frontend, direct dependencies; transitive ones are listed in package-lock.json)

| Package | Version | License |
|---|---|---|
| @playwright/test | 1.63.0 | Apache-2.0 |
| @tailwindcss/vite | 4.1.11 | MIT |
| @tanstack/react-query | 5.62.0 | MIT |
| @testing-library/jest-dom | 6.6.3 | MIT |
| @testing-library/react | 16.1.0 | MIT |
| @types/node | 22.10.2 | MIT |
| @types/react | 18.3.17 | MIT |
| @types/react-dom | 18.3.5 | MIT |
| @vitejs/plugin-react | 4.3.4 | MIT |
| @xyflow/react | 12.3.6 | MIT |
| echarts | 5.5.1 | Apache-2.0 |
| jsdom | 25.0.1 | MIT |
| lucide-react | 0.468.0 | ISC |
| react | 18.3.1 | MIT |
| react-dom | 18.3.1 | MIT |
| react-router-dom | 6.28.0 | MIT |
| tailwindcss | 4.1.11 | MIT |
| typescript | 5.7.2 | Apache-2.0 |
| vite | 6.0.5 | MIT |
| vitest | 2.1.8 | MIT |
| zod | 3.24.1 | MIT |
| zustand | 5.0.2 | MIT |

## Other

| Item | License / status |
|---|---|
| Chromium for Playwright tests | BSD-style (Chromium); test-only, installed by `npx playwright install chromium` |
| SQLite (via Python stdlib) | Public domain |
| Optional: Ollama / llama.cpp and any model | Not bundled. User installs and accepts the model's own license. Disabled by default. |
| Brand placeholder `frontend/public/brand/ff-mark.svg` | Original to this repository |
| IFS trademarks / logos | Not included. The UI is "IFS-inspired" in color only. |
