# FEMORA AI

**Menopause intelligence, nutrition, wellbeing and global sisterhood.** This folder holds the leadership-demo prototype.

> All people and health data are **fictional**. AI responses are **simulated**. Not medical advice.
> Demo personas are named Bea and Nancy; their health details are invented.

## Run it

```bash
cd femora/web
npm install
npm run dev        # http://127.0.0.1:5174
npm test           # 62 tests
npm run build
```

## What works today

| Area | Status |
|---|---|
| Executive showcase with honest status table and roadmap | Working |
| Copilot: 8 modes, multi-message, history, search, rename, archive, export, delete, voice input (browser), consented memory, sources, safety rules | Simulated responses |
| Food: 42 dishes from 10 regions, natural-language logging, editable portions, 14 nutrients, editable targets, evidence labels | Working (sample data) |
| My Joy Map | Working |
| Themes: Sky, Forest, Indigo × light/dark, all from `src/theme/tokens.css` | Working |
| Cycles, body, sisterhood map, healthcare, Guardian | Planned (navigable placeholders) |

See [docs/AUDIT.md](docs/AUDIT.md) for the architecture inventory, reuse map, plans and milestones.

## Deploy

GitHub Pages deployment is manual: enable *Settings → Pages → Source: GitHub Actions*, then run **FEMORA deploy to GitHub Pages** from the Actions tab.

---
Created by Florina Regius · florinaregius@yahoo.com
