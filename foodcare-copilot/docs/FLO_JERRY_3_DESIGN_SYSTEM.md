# Flo & Jerry 3.0 design system

Source of truth: `apps/control-room/tailwind.config.js` (tokens) and `src/index.css` (components).

## Colour tokens

| Token | Hex | Use |
|---|---|---|
| `midnight` | `#091321` | App background |
| `elevated` | `#17283C` | Panels, cards |
| `champagne` | `#D7B77A` | Primary actions, Jerry, eyebrows, focus of attention |
| `teal` | `#45C5B8` | Healthy states, links, selected items, data series |
| `ink` | `#F3F0E9` (Ivory) | Primary text; `ink-muted` / `ink-faint` for secondary |
| `risk` | red family | Only for risk, failure, overdue |

Rule: colour carries meaning. Risk colours appear only for risk; gold only for things to act on.
Status is never conveyed by colour alone (text labels on every chip and chart).

## Type and layout

System sans-serif; light weight for hero titles, semibold for section titles; `eyebrow` small
uppercase tracking for context labels. Max content width 7xl; 7-section left navigation
(Overview, My Priorities, Operations, Global Network, Jerry AI, Technology, Reports) with only the
active section expanded; mobile menu below `lg`.

## Components (`index.css`)

`btn-primary` (champagne), `btn-ghost`, `panel`, `chip`, `eyebrow`, `skeleton`, `selected-glow`,
`visual-card` (glass card with soft glow for visuals), `metric-tile` (glowing KPI tile),
`radar-sweep`, `jerry-hero` (welcome gradient), `welcome-card` (suggestion cards).

## Visual language from the reference images

The references (assistant greeting with suggestion cards, glowing metric cards, luminous network
graphs, dark dashboards) were used as *style direction only*: dark navy surfaces, glow on data
marks, generous spacing, a personal greeting ("Hey Eli, I'm Jerry."). No third-party artwork or
superhero imagery was copied; "Thor mode" is a metaphor only.

## Accessibility

Keyboard-reachable graph nodes and controls; `aria-label` on every chart summarising its
content; **Show data** tables as text alternatives; `prefers-reduced-motion` disables autoplay
and transitions; focus moves into the X-Ray dialog (Close button) when it opens.
