# Design language

The visual direction comes from the reference shots the product owner supplied. They were used as **style references only**: no third-party artwork, stock portraits, logos or brand assets are in the product. Everything below is drawn in code.

| Reference idea | Career_flo implementation |
|---|---|
| Near-empty canvas, soft colour blooms, a few floating rounded cards | `.bloom` background, `.card` (24 px radius, soft shadow), lots of whitespace, one focal element per screen |
| Multiplayer cursors with name chips | `AgentCursor`: each AI agent appears as a coloured cursor hovering over the work it is doing, live during chat runs |
| Contribution heatmap | `ActivityHeatmap`: applications per day (landing, Application Tracker) |
| "Search and apply" job board | `JobDiscovery` + `JobCard`: centred serif headline, category pills, bookmark, 2×2 meta grid, black Apply button, "Posted N days ago" strip, selected card outlined in sky blue |
| Team portrait row, greyscale with one in colour | `CareerProgression`: Junior → Principal role cards with generated abstract busts. Past and future steps are greyscale; "You are here" is in colour and lifted |
| Books stacked as stairs with a bookmark | `BookStairs`: the learning mark |
| Ladder / Lattice / Wave / Portfolio illustrations | `PATH_ART`: four original flat SVG scenes. They organise Skills & Learning: books, certifications and proof projects per skill |

Palette: midnight `#101828`, violet `#7357FF`, sky `#38BDF8`, emerald `#10B981`, plus warm accents (amber, coral) for cursors and illustrations. Type: Instrument Serif for headlines, Inter for UI. Light and dark themes are supported, and `prefers-reduced-motion` is respected.
