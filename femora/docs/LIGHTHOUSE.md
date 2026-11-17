# Lighthouse results

Measured 17 Nov 2026 with **Lighthouse 12.8.2** (Chrome 153, headless), default simulated throttling: mobile (slow 4G, 4× CPU) and the desktop preset. The production build was served with gzip at `/Data-sets/`, as GitHub Pages would serve it. Every run is a **first visit** (empty storage, welcome dialog showing). Raw JSON reports are not committed.

| Page | Mobile perf | Desktop perf | Accessibility | Best practices | SEO | Mobile LCP | Mobile CLS | Mobile TBT |
|---|---|---|---|---|---|---|---|---|
| Homepage `/` | 97 | 100 | 100 | 100 | 100 | 2.3 s | 0 | 40 ms |
| App home | 97 | 100 | 100 | 100 | 100 | 2.3 s | 0 | 30 ms |
| Talk to Muse | 94 | 100 | 100 | 100 | 100 | 2.7 s | 0 | 70 ms |
| Food & nutrition | 84 | 100 | 100 | 100 | 100 | 3.5 s | 0.006 | 280 ms |
| Menopause journey | 85 | 99 | 100 | 100 | 100 | 2.7 s | 0.006 | 390 ms |
| Health dashboard | 89 | 99 | 100 | 100 | 100 | 3.3 s | 0.006 | 60 ms |
| Guardian | 94 | 100 | 100 | 100 | 100 | 2.7 s | 0.006 | 110 ms |
| Global sisterhood | 95 | 88 | 100 | 100 | 100 | 2.6 s | 0 | 90 ms |

The homepage on mobile was measured three times in a row: 97 / 97 / 97, layout shift 0 each time.

## What changed to get here (first run → final)
| Issue found | Fix |
|---|---|
| Champagne accent text 3.15:1, green badges 4.28:1, warning badges 3.84:1 | Accents darkened per theme to ≥4.5:1 (onyx `#7c5f2b`, emerald `#7f6431`, midnight `#6f6248`); good `#2f6a4a`; warn `#7a5410` |
| Heading levels skipped (h1 → h3) | Card titles are `h2`; sub-headings `h3` |
| Calendar used `role="grid"` without rows | Now a labelled list of days with full date labels |
| Layout shift from footer jumping while pages load, chart cards resizing, rotating hero text, late web fonts | Reserved page and chart heights; hero lines share one grid cell; fonts **self-hosted** (variable woff2, preloaded, no Google request) |
| Map blocked the main thread for 3.4 s on mobile | Phones show a 25 KB map preview until "Explore the interactive map" is tapped; desktops load the map when idle |
| Charting library parsed with the Food and Journey pages | Charts split into lazy chunks loaded after first paint |
| Welcome dialog started invisible, so the largest paint couldn't be measured | Entrance animation is transform-only |

## Known remaining costs
- Mobile Food (84) and Journey (85): the remaining blocking time is the charting library (~106 KB gzip) loading once the browser is idle.
- Sisterhood desktop (88): MapLibre (~273 KB gzip) loads when idle on larger screens; phones avoid it until asked.
