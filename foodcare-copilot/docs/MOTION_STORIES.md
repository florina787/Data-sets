# Motion Stories

A Motion Story is an animated, step-by-step explanation built from a validated `motion_story`
visual: nodes, edges and steps. Each step highlights the nodes it talks about.

## Stories

| Story | Ask Jerry | Shows |
|---|---|---|
| `architecture` | "Animate how these systems work together" | Question → Jerry → policy engine → tools → data sources (with real connector states) → answer |
| `supplier_disruption` | "Animate a supplier disruption" (optionally for a site) | How a disruption at one site flows to plants, DCs and stores; modelled, labelled |
| `farm_to_market` | "Animate the farm-to-market journey" | Field → intake → processing → cold chain → DC → store |

Every story carries a disclaimer saying it is an explanatory sequence, not a live trace.

## In the app

Play, pause, replay and 0.5×/1×/2× speed. With `prefers-reduced-motion`, there is no autoplay
and all steps are listed statically. **Show data** lists every step as text.

## Export

`GET /api/motion/{story}.gif?site=GEO-XXX-00` renders a GIF on the server with Pillow
(`backend/app/motion.py`) from the same policy-filtered story, so a GIF can never contain more
than the story itself. Unknown stories return 404; an invalid `site` returns 422.

**MP4 is not implemented.** It would need an encoder such as FFmpeg; we did not add that
dependency. GIF is the supported export.
