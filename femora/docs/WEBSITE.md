# FEMORA Muse launch website

The public site and the app are one React + Vite build. Public pages are marketing; `/app` is the product.

## Routes
| Path | Page | Notes |
|---|---|---|
| `/` | Cinematic homepage | Headline "Every woman's journey deserves to be understood."; trial CTA goes to the **waitlist** (email) because trials aren't active |
| `/features` | Feature explorer | 8 categories: value, real visual or clip, how it works, status, privacy notes, "Coming soon" items |
| `/demo` | Interactive demo | Seeds **synthetic** data for "Demo Bea" into a separate `femora:demo:` storage namespace, then opens the app with a demo banner (Reset / Exit) |
| `/club` | Sisterhood club | Constellation of **fictional** preview profiles, circle cards, event *formats*, lounge and Sister Match previews, the 15 verified organisations, safety & consent |
| `/how-it-works` | Six steps | Recorded clips with text descriptions |
| `/gallery` | Media gallery | 10 clips (WebM/MP4 with posters, GIF fallback), category filters, nothing autoplays, one clip plays at a time |
| `/pricing` | Plans & trial | Proposed plans, entitlement table, trial dates, **no prices, no checkout** (see `SUBSCRIPTIONS.md`) |
| `/trust` | Science, trust & privacy | Can/cannot, data flows, evidence, consent & deletion, community privacy, safety escalation |
| `/app/*` | The app | Unchanged features |

## How it's built
- `web/src/site/`: `SiteLayout` (sticky nav, mobile menu, footer), `Reveal` (IntersectionObserver reveals), `Carousel` (scroll-snap, buttons, arrow keys, live announcements), `ClipPlayer` (poster first, loads on play), `Botanicals` (original SVG line art), `usePageMeta`, `media.ts` (asset registry), `demoData.ts`.
- Motion is CSS only (no animation library), and every animation is disabled under `prefers-reduced-motion`.
- Media in `web/public/media/`: WebP screenshots (640/1280), phone shots, MP4 + WebM clips with WebP posters (4.9 MB total), GIF fallbacks.
- Fonts are self-hosted. No third-party requests on page load.

## GitHub Pages & SEO
- `BrowserRouter` with the base path (`/femora/`).
- `scripts/postbuild.mjs` writes per-page `index.html` files with unique title, description, canonical link, Open Graph and Twitter tags. It also writes `app/index.html` (noindex), a `404.html` fallback so app routes load on refresh, `sitemap.xml`, `robots.txt`, `.nojekyll`, and a production Content Security Policy.
- JSON-LD `SoftwareApplication` (no ratings or offers). The sharing image is `og.jpg`, built from real app screens.

## Running the demo
Open `/demo` → **Start the demo**. Everything you see uses synthetic data. Muse's replies come from its offline library, not a live AI model. **Reset demo** restores the sample data; **Exit demo** deletes it and returns home. Real records (if any) are never touched.

## Deploying (owner-approved, manual)
GitHub Pages for `florina787/Data-sets` already serves **VEENA.AI**, so FEMORA deploys from its own repository:
1. Create an empty public repository `florina787/femora` on GitHub.
2. Push this project to it (see the session notes), then go to *Settings → Pages → Source: GitHub Actions*.
3. Run **FEMORA deploy to GitHub Pages** from the Actions tab. The site goes live at `https://florina787.github.io/femora/`.

The workflow refuses to run in any other repository, so it can't overwrite VEENA.

## Deployment readiness checklist
- [x] Production build passes; 151 tests pass; promptfoo evals pass
- [x] All public routes load directly and on refresh; app deep links load via `404.html`
- [x] No console errors, no CSP violations, no missing assets (desktop + mobile QA)
- [x] Lighthouse: accessibility, best practices and SEO 100 on all 8 public pages; mobile performance 90–98
- [x] No secrets in the bundle (CI scan); no payment code; no analytics
- [x] Demo clearly labelled and isolated; no invented members, events, prices, ratings or endorsements
- [ ] Repository `florina787/femora` created and Pages source set to GitHub Actions (owner)
- [ ] Owner runs, or approves, the deploy workflow
