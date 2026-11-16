# FEMORA Muse

**A personal companion for women's health, menopause, nutrition, wellbeing and community.**

Muse supports, and never replaces, clinicians. All data stays in your browser.

## Run it

```bash
cd femora/web
npm install
npm run dev        # http://127.0.0.1:5174
npm test           # 83 tests
npm run build
```

Optional local AI: run a llama.cpp server (`llama-server -m your-model.gguf --port 8080`), then in **Profile & privacy → Muse model**, test the connection and enable it.

## Available today

| Area | What works |
|---|---|
| Talk to Muse | 8 modes, history, search, rename, archive, export, delete, voice input (browser), consented memory, sources, crisis and urgent-symptom rules, humour and stories, brief answers; offline library or your llama.cpp model |
| Home | Proactive suggestions from your own records only |
| Food & nutrition | 42 dishes from 10 regions, natural-language logging, photo-assisted logging, sugar % of calories, nutrient charts, editable targets |
| Health planner | Medication & supplement reminders (taken/skipped/snoozed, refills, export), check-ups with saved questions; no invented intervals |
| MedScan | Your lab values explained against your report's range; rule-based symptom check |
| Discover | HTTP-verified official programmes, verified event feed (empty until partners connect), events you save, spiritual preferences, offers opt-in |
| Notifications | Categories, quiet hours, limits, digest, snooze, dismiss, feedback, private medication text, browser alerts |
| Connections | Contacts, WhatsApp, email, SMS, share sheet, calendar files; you always press send |
| Design | Onyx & Champagne, Emerald & Ivory, Midnight & Pearl themes × light/dark, all from `web/src/theme/tokens.css` |

Coming next: menopause journey, health dashboard, Guardian, sisterhood map, onboarding tour. See [docs/MUSE_PLAN.md](docs/MUSE_PLAN.md).

## Deploy

Not deployed. With approval: enable *Settings → Pages → Source: GitHub Actions*, then run **FEMORA deploy to GitHub Pages**.

---
Created by Florina Regius · florinaregius@yahoo.com
