# Third-party notices

Licences were read from installed package metadata on 2026-11-04. An automated scan of all 54 installed Python
distributions (including transitive dependencies) found **no GPL, LGPL, AGPL or SSPL** licences.

## Python (runtime and tooling)
| Package | Version | Licence |
|---|---|---|
| fastapi | 0.118.0 | MIT |
| starlette | 0.48.0 | BSD-3-Clause |
| uvicorn | 0.37.0 | BSD-3-Clause |
| pydantic | 2.11.9 | MIT |
| httpx | 0.28.1 | BSD-3-Clause |
| langgraph | 1.0.1 | MIT |
| langgraph-checkpoint-sqlite | 2.0.11 | MIT |
| numpy | 2.3.3 | BSD-3-Clause |
| pillow | 11.3.0 | MIT-CMU (HPND) |
| psutil | 7.1.0 | BSD-3-Clause |
| tzdata | 2025.2 | Apache-2.0 |
| pytest (tests) | 8.4.2 | MIT |
| ruff (lint) | 0.13.3 | MIT |

## JavaScript (interface and tests)
| Package | Version | Licence |
|---|---|---|
| react, react-dom | 18.3.1 | MIT |
| react-router-dom | 6.28.0 | MIT |
| vite | 5.4.11 | MIT |
| tailwindcss | 3.4.17 | MIT |
| typescript | 5.6.3 | Apache-2.0 |
| @playwright/test (tests) | 1.56.1 | Apache-2.0 |

## Artwork
Jerry (fries carton), the potatoes and the fries illustrations are original SVG drawings made for this project. No third-party artwork, logos or branding are included.

## Re-checking
Re-run the licence scan after adding any dependency. The command is in `docs/MODEL_EVALUATION.md`, under "Licence scan".

## Added in Flo & Jerry 3.0

| Package | Version | Licence | Used for |
|---|---|---|---|
| reportlab | 4.2.5 | BSD | Executive Export Studio PDFs (built in memory) |
| chardet | 7.7.0 | 0BSD | Dependency of reportlab |
| three | 0.169.0 | MIT | 3D supply-chain globe (lazy-loaded) |
| d3-geo | 3.1.1 | ISC | 2D map projection |
| topojson-client | 3.1.0 | ISC | Decoding world borders |
| world-atlas | 2.0.2 | ISC (data: Natural Earth, public domain) | Country borders, offline |
