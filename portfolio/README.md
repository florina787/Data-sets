# Florina Regius — AI Engineering Lab

**Lead AI Engineer · Agentic AI · Generative AI · Forward Deployed AI Engineer · AI Architect**

> I design, build and productionize enterprise AI systems.
> From prototype → architecture → agents → integration → deployment → observability → scale.

![HTML5](https://img.shields.io/badge/HTML5-semantic-1b1d21?logo=html5&logoColor=white)
![CSS](https://img.shields.io/badge/CSS-no%20framework-1b1d21?logo=css&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-vanilla%20ES%20modules-1b1d21?logo=javascript&logoColor=white)
![Dependencies](https://img.shields.io/badge/runtime%20dependencies-0-1f4ef5)
![License](https://img.shields.io/badge/license-MIT-1f4ef5)

An interactive engineering portfolio that shows how production AI systems are designed, not just a list of skills. Every demo runs **locally in the browser**: no API keys, no backend, no tracking.

**Live site:** `https://GITHUB_USERNAME.github.io/Data-sets/` *(placeholder: set `SITE_URL` in `assets/js/config.js`)*

---

## What's inside

| Section | What it shows |
|---|---|
| **How I build AI systems** | Discover → Design → Prototype → Evaluate → Secure → Deploy → Observe → Optimize → Scale |
| **Agentic AI Lab** | Clickable multi-agent graph (Orchestrator → Retrieval / Reasoning / Tool → Validator) with animated states and optional failure injection (retry + backoff, degraded retrieval) |
| **RAG Explorer** | A real in-browser pipeline over a synthetic corpus: query expansion, hashed embeddings, BM25 + vector hybrid retrieval, reranking, token-budgeted context and an extractive answer with citations that refuses when evidence is missing |
| **MCP Tool Lab** | JSON-RPC 2.0 `initialize` → `tools/list` → `tools/call` traces for Jira, Confluence, SharePoint, GitHub, a database and a REST API |
| **System design case study** | Enterprise Knowledge Copilot: requirements, architecture, RBAC, JWT propagation, document permissions, PII, prompt injection, citations, caching, latency and cost |
| **POC → Production** | What changes between a notebook and a production service |
| **AI observability** | Dashboard labelled **DEMO TELEMETRY**: requests, latency, tokens, retrieval quality, agent/tool success, cache hit rate, cost/request, plus a trace waterfall |
| **When AI fails** | Ten failure modes mapped to resilience patterns (filterable) |
| **Secure AI by design** | Identity → authorization → guardrails → permission-aware retrieval → output validation → audit |
| **Evaluating AI systems** | Retrieval, generation, agent and operational metrics, and how each is measured |
| **Architecture decisions** | Eight interactive trade-offs (RAG vs fine-tuning, LangChain vs LangGraph, REST vs MCP, …) |
| **AI cost engineering** | Cost path plus an illustrative token-budget estimator |
| **Projects / Experience / Skills** | Case-study cards, capability-based experience, skills map |

**Also included:** an **Engineer ⇄ Recruiter mode** toggle (persisted locally), a **terminal** with predefined safe commands (`whoami`, `skills --core`, `architecture --agentic`, `projects`, `contact`, `goto <section>`, `help`) and a **Ctrl/⌘ + K command palette**.

## Quick start

```bash
cd portfolio
python3 -m http.server 8080
# open http://localhost:8080
```

Any static server works (`npx serve .` for example). A server is required because the site uses ES modules, which browsers won't load from `file://`.

## Configure (change values once)

Edit **`assets/js/config.js`**:

```js
GITHUB_USERNAME: 'GITHUB_USERNAME',   // e.g. 'octocat'
LINKEDIN_URL:    'LINKEDIN_URL',      // e.g. 'https://www.linkedin.com/in/your-handle'
EMAIL_ADDRESS:   'EMAIL_ADDRESS',     // e.g. 'you@example.com'
SITE_URL:        'https://GITHUB_USERNAME.github.io/Data-sets/',
```

The header, contact cards, project links, terminal, command palette and JSON-LD all read from this file. While a value is still a placeholder, its link renders as an inert labelled placeholder instead of a broken link.

Crawlers don't run JavaScript, so the `<head>` tags (canonical, OpenGraph, Twitter card, JSON-LD) are generated from the same file:

```bash
node scripts/build.mjs   # syncs <head> metadata from config.js and builds dist/
```

The deploy workflow runs this automatically, so editing `config.js` is enough for production.

No phone number or physical address is published anywhere, and the email address is deliberately left out of the structured data.

## Project structure

```
portfolio/
├── index.html               # all content (semantic HTML; demos hydrate lazily)
├── 404.html
├── assets/
│   ├── css/styles.css       # design system: tokens, grid, components, responsive, reduced motion
│   ├── img/                 # favicon.svg, og-image.png (1200×630)
│   └── js/
│       ├── config.js        # ← the only file with personal values
│       ├── main.js          # view mode, nav, reveal, lazy-loading of demos
│       ├── util.js          # helpers (escaping, seeded PRNG, JSON highlighting)
│       ├── terminal.js      # fixed command table: no eval, no shell
│       ├── palette.js       # Ctrl/⌘+K command palette (combobox + listbox)
│       ├── agent-lab.js     # multi-agent state machine simulation
│       ├── rag.js           # BM25 + hashed-vector hybrid retrieval, rerank, context packing
│       ├── rag-corpus.js    # synthetic "NovaGrid Corp" documents
│       ├── mcp.js           # MCP JSON-RPC message simulation
│       ├── observability.js # DEMO TELEMETRY dashboard
│       ├── failures.js · decisions.js · cost.js
│       └── analytics.js     # optional, disabled by default
├── scripts/
│   ├── build.mjs            # meta sync + dist/ build + robots.txt + sitemap.xml
│   └── check.mjs            # secret scan + demo-label check + placeholder report
├── package.json             # scripts only, no dependencies
├── .env.example · .gitignore · LICENSE · CONTRIBUTING.md · SECURITY.md
└── README.md
../.github/workflows/deploy.yml   # GitHub Pages deployment
```

## Deploy to GitHub Pages

1. Push to `master` (or `main`).
2. In the repo, open **Settings → Pages → Build and deployment → Source** and choose **GitHub Actions**.
3. The workflow `.github/workflows/deploy.yml` runs `check.mjs` (it fails on anything that looks like a secret), builds `dist/` and publishes it.

Your site will be at `https://<user>.github.io/<repo>/`. Set `SITE_URL` to match.

## Analytics (optional, off by default)

No tracking ships by default. To add privacy-friendly, cookie-less analytics later:

1. Choose a provider: [Plausible](https://plausible.io), [GoatCounter](https://www.goatcounter.com) or self-hosted [Umami](https://umami.is).
2. In `config.js`, set `ANALYTICS.enabled: true`, set `provider`, and fill in `domain` (Plausible/GoatCounter) or `scriptSrc` + `websiteId` (Umami).
3. Redeploy. The loader in `assets/js/analytics.js` injects the provider's script only when it is fully configured, and skips it for visitors with **Do Not Track** or **Global Privacy Control** enabled.

## Honesty policy

- All demo data is **synthetic** and labelled **DEMO / SIMULATED / LOCAL SIMULATION**. `check.mjs` verifies the labels are present.
- "NovaGrid Corp" and every document, ticket and metric in the demos are fictional.
- Project outcomes are not invented. Where none is published, the card says *"Outcome details available during technical discussion."*
- No certifications, rankings or affiliations are displayed.

## Accessibility & performance

- Semantic landmarks, a skip link, one `h1`, labelled controls, ARIA tabs/combobox/live regions, visible focus rings, full keyboard support (palette, terminal history and tab completion, arrow-key tabs).
- `prefers-reduced-motion` disables animations and auto-updating telemetry.
- Zero runtime dependencies, no web fonts (system font stacks), and **demos are lazy-loaded** with dynamic `import()` when they approach the viewport. Total JS is about 90 KB uncompressed (about 30 KB gzipped). The initial load fetches only about 10 KB gzipped of core modules.

## Security

See [SECURITY.md](SECURITY.md). Short version: no secrets, no backend, no arbitrary execution, all rendered data escaped, and a secret scan on every deploy.

## License

Code: [MIT](LICENSE). Written content © Florina Regius.
