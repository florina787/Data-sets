<div align="center">

<img src="docs/media/banner.svg" alt="FEMORA Muse: a companion that walks beside you. Women's health, menopause and life." width="100%">

<br>

![Tests](https://img.shields.io/badge/tests-151%20passing-2f6a4a?style=for-the-badge)
![Evals](https://img.shields.io/badge/agent%20evals-15%2F15-2f6a4a?style=for-the-badge)
![Accessibility](https://img.shields.io/badge/Lighthouse%20a11y-100-2f6a4a?style=for-the-badge)
![React](https://img.shields.io/badge/React%2019-17140f?style=for-the-badge&logo=react&logoColor=e7cf9f)
![TypeScript](https://img.shields.io/badge/TypeScript-17140f?style=for-the-badge&logo=typescript&logoColor=e7cf9f)
![Real data](https://img.shields.io/badge/trained%20on-10%2C375%20real%20women-7c5f2b?style=for-the-badge)

**[Launch website](docs/WEBSITE.md) · [The story](#-the-story) · [See it move](#-see-it-move) · [Real data](#-trained-on-real-data) · [How Muse thinks](#-how-muse-thinks) · [Measured](#-measured-not-claimed) · [Status](#-honest-status) · [Run it](#-run-it)**

</div>

<br>

<p align="center">
  <img src="docs/media/muse-landing.gif" alt="FEMORA Muse homepage: onyx and champagne hero with the line 'A companion that walks beside you' cycling through 'listens first', 'knows your plate', 'remembers your check-ups'" width="88%">
</p>

---

## ✦ The launch website

A cinematic public site sits in front of the app: homepage, features, an **interactive demo with synthetic data**, the Sisterhood club, how it works, a gallery, pricing (proposed, with no checkout) and science & trust.

- **Lighthouse:** accessibility, best practices and SEO **100** on all 8 pages; mobile performance 90–98.
- **Where it will live:** `https://florina787.github.io/Bea/`, published from its own repository so the existing VEENA.AI site isn't affected.
- **Details:** [docs/WEBSITE.md](docs/WEBSITE.md) · billing design: [docs/SUBSCRIPTIONS.md](docs/SUBSCRIPTIONS.md)

---

## ✦ The story

> *"I'm fine."* It's what so many women say in their forties and fifties. They say it while they're up at 3am again, holding back tears in a meeting for no reason they can name, running a company or a family, caring for parents and children, and quietly wondering whether this is just how life feels now.

Menopause is not an illness. It's a natural transition that most women reach between 45 and 55 ([WHO](https://www.who.int/news-room/fact-sheets/detail/menopause)). Yet it often arrives with little warning and less support. The changes are wide-ranging: sleep, mood, memory, joints, skin, hair, appetite. They can begin years before periods stop. Care is scattered. And the thing that helps most, someone who listens and understands, is often missing.

**FEMORA Muse was built to change that.**

Imagine **Bea**: 37, running a fast-growing company in the United States. She doesn't think menopause is her story yet, but she wants to understand what's ahead, keep on top of her screenings, eat well across the cuisines she loves, and have somewhere to put the worries she doesn't say out loud.

Now imagine **Nancy** in Nashville. She wants to stay strong and sharp for the decades ahead, find a walking group or a yoga class nearby, and never miss a check-up.

They aren't the same woman, and Muse doesn't treat them as if they were. Muse doesn't assume Bea is menopausal because she opened the app, or that Nancy is religious because she asked about meditation. **Muse knows only what each woman chooses to share.**

> Bea and Nancy are example configurations used to describe the product. They are not real accounts, and the app holds no health records for them.

### Our purpose

<table>
<tr>
<td width="33%" valign="top">

#### 🕊️ To be heard
A companion who listens first, encourages often, can make you laugh, and knows when to say *"please talk to a clinician."*

</td>
<td width="33%" valign="top">

#### 🌍 To be understood
Food from every kitchen. Every culture, every belief or none, every stage of life, every corner of the world.

</td>
<td width="33%" valign="top">

#### 🛡️ To be safe
Private by default. Nothing invented. Nothing sent without your tap. Safety rules that never depend on an AI's mood.

</td>
</tr>
</table>

---

## ✦ What Muse does

```mermaid
%%{init: {'theme':'base','themeVariables':{'primaryColor':'#17140f','primaryTextColor':'#f7f1e6','primaryBorderColor':'#7c5f2b','lineColor':'#7c5f2b','secondaryColor':'#f0ebe2','tertiaryColor':'#fbf8f2','fontFamily':'Georgia'}}}%%
mindmap
  root((FEMORA<br/>Muse))
    Talk to Muse
      8 conversation modes
      Encouragement, humour & stories
      Consented memory
      Crisis & urgent-symptom rules
      Offline or your own llama.cpp
    Menopause journey
      Cycle calendar & symptoms
      Stage education with uncertainty
      Next-period forecast
      Doctor-ready summary
    Body & mind
      14 measures you record
      Trends, ranges, comparisons
      Guideline notes, no scores
    Food & nutrition
      42 dishes · 10 world regions
      Log in a sentence
      Sugar % of calories
    Health planner
      Medication & supplements
      Check-ups & questions
      Notifications you control
    Guardian
      One-tap emergency call
      SOS drafts to your people
      Check-ins & emergency card
    Global sisterhood
      Verified organisations map
      Privacy-preserving markers
    Help
      Welcome & guided tours
      Help centre & Ask Muse how
```

---

## ✦ See it move

<table>
<tr>
<td width="50%" valign="top">

### 👋 A warm welcome
Five gentle steps: meet Muse, choose what you'd like help with, set your privacy, tell Muse your city. Then **"Show me around"** spotlights the real controls on each page. Skip anything; restart any time.

</td>
<td width="50%"><img src="docs/media/muse-onboarding.gif" alt="Welcome flow with interests, privacy and city, then a guided tour spotlighting the navigation, Muse's greeting and the notification bell"></td>
</tr>
<tr>
<td width="50%"><img src="docs/media/muse-chat.gif" alt="Conversation: loneliness and poor sleep get a warm reply; 'When was my last period?' is answered from records; then a joke"></td>
<td width="50%" valign="top">

### 💬 Talk to Muse
Long, warm conversations about anything: loneliness, sleep, family, work, confidence. Muse validates first, encourages sincerely and asks a caring question back. Ask *"when was my last period?"* or *"how much protein did I eat?"* and the answer comes **from your own records**, never a guess.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🌙 Menopause journey
A cycle calendar, symptom tracking and patterns explained with honest uncertainty (STRAW+10). A **next-period forecast** comes from your own cycles, backtested on your history. **"Your age in context"** comes from a model trained on 10,375 real women. Download a doctor-ready summary in one tap.

</td>
<td width="50%"><img src="docs/media/muse-journey.gif" alt="Journey page: cycle calendar, pattern notes, next-period forecast with range, age-in-context curve from national data, cycle-length and symptom charts"></td>
</tr>
<tr>
<td width="50%"><img src="docs/media/muse-food.gif" alt="Typing meals in plain language; the energy donut, sugar percentage gauge and weekly goal chart update"></td>
<td width="50%" valign="top">

### 🍲 Food from every kitchen
Type *"2 idli and sambar with chai for breakfast"* and it's logged. Idli, jollof, laksa, tacos, shakshuka, congee: **42 dishes from 10 regions** with editable portions, 14 nutrients and your **sugar percentage** against WHO guidance.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 📈 Body, movement & mind
Fourteen measures you record yourself: blood pressure, glucose, HbA1c, sleep, steps, joints, skin, hair, nails, brain fog, mood. Change the date range, **compare two measures**, and read ACC/AHA and ADA guideline ranges in plain words. **No scores, no diagnoses.**

</td>
<td width="50%"><img src="docs/media/muse-body.gif" alt="Health dashboard: sleep compared with mood, then blood pressure with a guideline-range note, then steps"></td>
</tr>
<tr>
<td width="50%"><img src="docs/media/muse-guardian.gif" alt="Guardian page: red emergency panel with Call 911 and SOS to my people, message draft with optional location, trusted contacts, check-ins and a capability table"></td>
<td width="50%" valign="top">

### 🛡️ Guardian
Call your local emergency number in one tap. **SOS to my people** opens SMS or WhatsApp with your message (and your location only if you allow it); *you* press send, and Muse never claims delivery it can't confirm. Check-ins, an emergency card, and an honest list of what still needs a server or the mobile app.

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🌍 Global sisterhood
An interactive world map of **15 organisations verified at their official websites**: menopause societies, support groups, public health and wellness directories. Markers show the country or city served, **never an address**, and your own location is never shown.

</td>
<td width="50%"><img src="docs/media/muse-sisterhood.gif" alt="World map with clustered markers; selecting the British Menopause Society zooms to the UK with a verified detail card; then the Indian Menopause Society"></td>
</tr>
<tr>
<td width="50%"><img src="docs/media/muse-themes.gif" alt="Switching between Emerald & Ivory, Midnight & Pearl and Onyx & Champagne themes in light and dark mode"></td>
<td width="50%" valign="top">

### ✨ Three luxury themes
**Onyx & Champagne**, **Emerald & Ivory**, **Midnight & Pearl**, each in light and dark, all passing WCAG AA contrast. Every colour lives in one file, [`tokens.css`](web/src/theme/tokens.css), so a full redesign never touches a feature.

</td>
</tr>
</table>

### A closer look

<table>
<tr>
<td width="50%"><img src="docs/media/screen-home.jpg" alt="Muse home greeting Bea about her real upcoming cervical screening"><br><sub><b>Home:</b> suggestions only from what she's recorded</sub></td>
<td width="50%"><img src="docs/media/screen-journey.jpg" alt="Journey forecast and age-in-context chart"><br><sub><b>Journey:</b> personal forecast and real-data context</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/media/screen-body.jpg" alt="Health dashboard comparing sleep with mood"><br><sub><b>Body & mind:</b> trends and comparisons</sub></td>
<td width="50%"><img src="docs/media/screen-planner.jpg" alt="Health planner with today's doses and check-ups"><br><sub><b>Planner:</b> doses, refills, check-ups, questions</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/media/screen-guardian.jpg" alt="Guardian SOS panel with message draft"><br><sub><b>Guardian:</b> safety first, always visible</sub></td>
<td width="50%"><img src="docs/media/screen-sisterhood.jpg" alt="Sisterhood map with a verified organisation"><br><sub><b>Sisterhood:</b> verified, privacy-preserving</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/media/screen-chat.jpg" alt="Muse answering about menopause age and next period without guessing"><br><sub><b>Muse:</b> population context, never a personal prediction of the final period</sub></td>
<td width="50%"><img src="docs/media/screen-food.jpg" alt="Food diary with sugar percentage"><br><sub><b>Food:</b> energy split, sugar %, weekly goals</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/media/screen-medscan.jpg" alt="MedScan explaining a low vitamin D result"><br><sub><b>MedScan:</b> your lab values against your report's range</sub></td>
<td width="50%"><img src="docs/media/screen-help.jpg" alt="Help centre with an article and Show me button"><br><sub><b>Help centre:</b> answers, animations, tours</sub></td>
</tr>
<tr>
<td width="50%"><img src="docs/media/screen-discover.jpg" alt="Discover page with verified official programmes"><br><sub><b>Discover:</b> verified sources only; nothing invented</sub></td>
<td width="50%"><img src="docs/media/screen-dark.jpg" alt="Emerald & Ivory theme in dark mode"><br><sub><b>Emerald & Ivory, dark</b></sub></td>
</tr>
</table>

<p align="center"><img src="docs/media/mobile-showcase.jpg" alt="Four phone screens: homepage, Muse home, menopause journey and Guardian" width="100%"><br><sub>Mobile-first: every page works at phone size.</sub></p>

> The tour above uses example entries typed in for the recording (meals, cycles, symptoms, a few measurements, one reminder, one appointment). A fresh install starts completely empty.

---

## ✦ Trained on real data

No synthetic women, no invented records. Muse's menopause-timing model is trained with open-source **lifelines**, **scikit-learn** and **statsmodels** on the U.S. national health survey (**CDC NHANES 2013–2018, 10,375 women**).

<p align="center"><img src="docs/media/chart-menopause-curve.svg" alt="Survey-weighted curve of the share of women who had reached natural menopause by age, from near 0% at 35 to near 100% at 60, crossing 50% at age 51, with a shaded confidence band and dashed lines for women born in the 1950s and 1960s" width="100%"></p>

| What we found | Honest reading |
|---|---|
| Median age at natural menopause **51.0** | Matches the medical literature |
| At 48: **24%** (95% CI 22–27%); at 51: **52%** (48–56%) | Population context shown in the app |
| Age-only model AUC **0.988**; adding BMI, smoking, menarche and pregnancies: **0.987** | Age carries almost all the signal, and we say so |
| Current smoking: ≈ **2 years earlier** | Expected direction |
| Born 1950s vs 1960s: same median (51), p = 0.58 | No generational shift detected |

Full model card: [ml/README.md](ml/README.md). Muse uses this as **context, never as a prediction of anyone's final period**.

### Graphs that mean something
These two are computed from Muse's own food table:

<p align="center"><img src="docs/media/chart-sugar.svg" alt="Added sugar as a percentage of calories per dish against WHO 5% and 10% lines" width="100%"></p>
<p align="center"><img src="docs/media/chart-protein.svg" alt="Protein per 100 kcal for dishes from around the world" width="100%"></p>

---

## ✦ How Muse thinks

A warm conversation layer on top of **deterministic tools** for everything that must be right. No language model decides a dose, a reminder time, a screening interval, a forecast, or whether something is an emergency.

```mermaid
%%{init: {'theme':'base','themeVariables':{'primaryColor':'#fbf8f2','primaryTextColor':'#17140f','primaryBorderColor':'#7c5f2b','lineColor':'#7c5f2b','actorBkg':'#17140f','actorTextColor':'#f7f1e6','actorBorder':'#7c5f2b','noteBkgColor':'#f0ebe2','noteBorderColor':'#7c5f2b','fontFamily':'Georgia'}}}%%
sequenceDiagram
    autonumber
    actor Her as She
    participant UI as Muse conversation
    participant Safety as Safety rules
    participant Tools as Deterministic tools
    participant Model as Offline library or llama.cpp
    Her->>UI: "When will my next period be?"
    UI->>Safety: crisis or urgent symptom?
    Safety-->>UI: clear
    UI->>Tools: forecast from her logged cycles (+ backtest)
    Tools-->>UI: Nov 30 · likely Nov 25 – Dec 5
    UI->>Model: persona + approved memory + facts
    Model-->>UI: warm, precise reply
    UI-->>Her: numbers from tools, words from Muse
    Note over Safety,Model: No data? Muse says it won't guess. Model down? Offline library takes over.
```

### Every notification earns its place

```mermaid
%%{init: {'theme':'base','themeVariables':{'primaryColor':'#17140f','primaryTextColor':'#f7f1e6','primaryBorderColor':'#7c5f2b','lineColor':'#7c5f2b','secondaryColor':'#f0ebe2','tertiaryColor':'#fbf8f2','fontFamily':'Georgia'}}}%%
flowchart LR
    A([Reminder or update]) --> B{Already sent<br/>or snoozed?}
    B -- yes --> X[(Stay quiet)]
    B -- no --> C{Critical<br/>safety?}
    C -- yes --> D[[Deliver now]]
    C -- no --> E{Category<br/>muted?}
    E -- yes --> X
    E -- no --> F{Quiet hours?}
    F -- yes --> G[/Morning digest/]
    F -- no --> H{Daily limit<br/>reached?}
    H -- yes --> G
    H -- no --> I{Digest mode?}
    I -- yes --> G
    I -- no --> D
    D --> J[Medication names hidden<br/>if privacy is on]
```

### Architecture

```mermaid
%%{init: {'theme':'base','themeVariables':{'primaryColor':'#fbf8f2','primaryTextColor':'#17140f','primaryBorderColor':'#7c5f2b','lineColor':'#7c5f2b','clusterBkg':'#f7f4ee','clusterBorder':'#d8ccb4','fontFamily':'Georgia'}}}%%
flowchart TB
    subgraph UI["🎨 Experience · React 19 + Vite · lazy routes"]
        T[Design tokens<br/>3 themes × light/dark]
        P[Home · Talk · Journey · Body · Food · Planner<br/>MedScan · Guardian · Sisterhood · Discover · Help]
        O[Welcome flow · tours · help centre]
    end
    subgraph Domain["⚙️ Deterministic domain logic · pure TypeScript"]
        N[Nutrition engine]
        J[Cycle maths & forecaster]
        R[Reminder scheduler]
        E[Notification engine]
        S[Safety rules]
        G[Guardian helpers]
        V[Verified registries]
    end
    subgraph ML["📊 Open-source ML · Python"]
        NH[(CDC NHANES<br/>10,375 women)] --> TR[lifelines · scikit-learn · statsmodels]
        TR --> MJ[model.json]
    end
    subgraph AI["🧠 Conversation gateway"]
        Rt[Router: safety first]
        Off[Offline response library]
        L[llama.cpp adapter]
    end
    subgraph Data["🔒 On-device data"]
        LS[(Versioned local storage<br/>export · delete)]
    end
    P --> Domain
    P --> Rt
    Rt --> S
    Rt --> Off
    Rt --> L
    MJ --> J
    Domain --> LS
    T -.-> P
```

### Tested, evaluated, not just built

```mermaid
%%{init: {'theme':'base','themeVariables':{'pie1':'#17140f','pie2':'#7c5f2b','pie3':'#2f6a4a','pie4':'#b5654a','pie5':'#6b645a','pie6':'#d7b57a','pie7':'#4a3c28','pieTitleTextSize':'20px','pieSectionTextColor':'#f7f1e6','fontFamily':'Georgia'}}}%%
pie showData title 134 automated tests
    "Companion quality (warmth, no dismissal, no diagnosis)" : 34
    "Planner, notifications, MedScan, discovery, llama.cpp" : 30
    "Guardian & health dashboard" : 12
    "Sisterhood map & onboarding" : 12
    "Journey & forecasting" : 22
    "Safety, citations & app flows" : 18
    "Nutrition engine" : 6
```

Plus **15/15 agent evaluations** with open-source [promptfoo](evals/README.md), run in CI. The very first evaluation run caught a real safety gap: *"I don't want to live anymore"* wasn't recognised as a crisis. It's fixed and now guarded by tests.

---

## ✦ Measured, not claimed

<p align="center"><img src="docs/media/chart-lighthouse.svg" alt="Lighthouse performance per page on mobile and desktop: homepage 97/100, app home 97/100, Talk to Muse 94/100, Food 84/100, Journey 85/99, Health dashboard 89/99, Guardian 94/100, Sisterhood map 95/88. Accessibility, best practices and SEO are 100 on every page" width="100%"></p>

Accessibility, best practices and SEO score **100 on every page**. Getting there meant real fixes: WCAG AA colours in every theme, proper heading order, an accessible calendar, zero layout shift, self-hosted fonts, a lightweight map preview on phones and lazy-loaded charts. Details: [docs/LIGHTHOUSE.md](docs/LIGHTHOUSE.md).

---

## ✦ Our promises

| | Promise | How it's enforced |
|---|---|---|
| 🚫 | **Nothing invented.** No fake events, offers, appointments, organisations or lab values. | Listings need a verified source with a date, or are added by you. Tests reject unverified items. |
| 📊 | **Real data, honest results.** | The model is trained on public NHANES data; null and weak results are reported, not hidden. |
| 🔒 | **Your data stays yours.** | Stored on your device. Export or delete everything. Fonts self-hosted: no third-party request on load. |
| 🤝 | **Consent before memory.** | Off until you approve a specific fact. Review and delete any time. |
| 📵 | **Nothing sent without your tap.** | SOS, WhatsApp, email and text open *your* apps with a draft. Muse never claims delivery. |
| 🩺 | **Supports clinicians, never replaces them.** | No diagnoses, no dose changes, no invented intervals, no final-period predictions. Crisis and urgent symptoms always go to real help first. |
| 🧘 | **Respects belief and solitude.** | Spiritual suggestions only if chosen (including "none"). Social nudges are gentle and optional. |

---

## ✦ Honest status

| Area | Status |
|---|---|
| Talk to Muse (offline library, safety rules, consented memory, llama.cpp adapter, "Ask Muse how to") | ✅ Available |
| Menopause journey, forecasting from real data, doctor-ready summary | ✅ Available |
| Health dashboard, food & sugar %, health planner, MedScan | ✅ Available |
| Guardian: emergency call, SOS drafts, check-ins, emergency card | ✅ Available |
| Global sisterhood map, Discover (verified sources), Connections | ✅ Available |
| Welcome flow, guided tours, help centre | ✅ Available |
| Automatic missed-check-in alerts, live location, push when closed | 🗺️ Needs a secure server or the mobile app |
| Clinician discovery (MedAccess integration), member circles, accounts & sync | 🗺️ Roadmap |
| Clinical validation | ⏳ Not yet; Muse is not a medical device |

```mermaid
%%{init: {'theme':'base','themeVariables':{'cScale0':'#17140f','cScale1':'#4a3c28','cScale2':'#7c5f2b','cScale3':'#2f6a4a','cScaleLabel0':'#f7f1e6','cScaleLabel1':'#f7f1e6','cScaleLabel2':'#f7f1e6','cScaleLabel3':'#f7f1e6','titleColor':'#7c5f2b','textColor':'#7c5f2b','fontFamily':'Georgia'}}}%%
timeline
    title The road ahead
    Today : Muse conversation : Journey & real-data forecasts : Body, food & planner : Guardian : Sisterhood map : Onboarding & help
    Next : Accounts & encrypted sync : Verified alert delivery : Clinician discovery
    Then : Calendar & email (OAuth) : Push notifications : Moderated circles
    Later : iOS & Android : On-device models : HealthKit & Health Connect : Clinical evaluation
```

---

## ✦ Run it

```bash
cd femora/web
npm install
npm run dev        # http://127.0.0.1:5174
```

```bash
npm test           # 151 tests
npm run build      # production build
```

**Optional: your own private AI.** Run a [llama.cpp](https://github.com/ggml-org/llama.cpp) server on your computer, then open *Profile & privacy → Muse model*, press **Test connection**, and enable it.

```bash
llama-server -m your-model.gguf --port 8080
```

**Re-train the model** (open source, public data):

```bash
cd femora/ml && python -m venv .venv && .venv/bin/pip install pandas numpy scikit-learn lifelines statsmodels scipy
.venv/bin/python download_nhanes.py && .venv/bin/python train_menopause.py
```

<details>
<summary><b>Project structure</b></summary>

```
femora/
├── web/                     React 19 + Vite + TypeScript app
│   ├── public/              self-hosted fonts, help clips, map preview, verified feed
│   ├── src/theme/           design tokens (all colours, type, radii)
│   ├── src/components/      UI primitives, app shell
│   ├── src/modules/
│   │   ├── conversation/    router, safety, persona, offline library, llama.cpp
│   │   ├── journey/         cycle maths, calendar, charts
│   │   ├── forecast/        trained model.json + personal forecaster
│   │   ├── body/            health dashboard
│   │   ├── nutrition/       food table, engine, charts, scanner
│   │   ├── reminders/       medication & check-up scheduling
│   │   ├── notifications/   delivery rules engine
│   │   ├── guardian/        safety tools
│   │   ├── sisterhood/      verified registry + MapLibre map
│   │   ├── onboarding/      welcome, tours, help centre
│   │   └── …                medscan, opportunities, connections, muse
│   └── src/__tests__/       134 tests
├── ml/                      NHANES pipeline + model card
├── evals/                   promptfoo agent evaluations
├── training/                companion dialogues
└── docs/                    MUSE_PLAN.md, LIGHTHOUSE.md, media
```

</details>

<details>
<summary><b>Tech stack</b> (all open source)</summary>

React 19 · TypeScript · Vite · Tailwind CSS 4 · React Router · Recharts · MapLibre GL + OpenFreeMap/OpenStreetMap · Lucide · Vitest + Testing Library · Playwright · Lighthouse · promptfoo · pandas · scikit-learn · lifelines · statsmodels · llama.cpp (optional) · GitHub Actions

</details>

<details>
<summary><b>Deploying to GitHub Pages</b></summary>

Deployment is manual and needs the owner's approval: enable *Settings → Pages → Source: GitHub Actions*, then run **FEMORA deploy to GitHub Pages** from the Actions tab.

</details>

📖 Plan: [docs/MUSE_PLAN.md](docs/MUSE_PLAN.md) · Model card: [ml/README.md](ml/README.md) · Evals: [evals/README.md](evals/README.md) · Performance: [docs/LIGHTHOUSE.md](docs/LIGHTHOUSE.md)

---

<div align="center">

### *Your health, your pace, your Muse.*

<sub>FEMORA Muse supports, and never replaces, professional medical care. In an emergency, call your local emergency number.</sub>

<br><br>

**Created by Florina Regius** · [florinaregius@yahoo.com](mailto:florinaregius@yahoo.com)

</div>
