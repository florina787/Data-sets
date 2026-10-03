# Contributing

Thanks for your interest! This is a personal portfolio, so feature contributions are limited. Bug reports, accessibility fixes and corrections are very welcome.

## Ground rules

- **Vanilla only.** HTML, CSS and ES modules. No frameworks, bundlers or runtime dependencies.
- **Honesty.** Simulated data must stay clearly labelled `DEMO` / `SIMULATED`. Don't add metrics, outcomes, rankings or affiliations that aren't real.
- **No secrets, ever.** Not in code, examples, screenshots or commit history.
- **Accessibility.** Keep keyboard support, visible focus, ARIA semantics and `prefers-reduced-motion` behaviour intact.

## Local workflow

```bash
cd portfolio
python3 -m http.server 8080   # or: npx serve .
# open http://localhost:8080
```

Before opening a pull request:

```bash
node scripts/build.mjs   # syncs <head> metadata from config.js, builds dist/
node scripts/check.mjs   # secret scan + demo-label check
```

## Code style

- 2-space indentation, single quotes, semicolons.
- One module per demo in `assets/js/`. Demos are lazy-loaded by `main.js`.
- Escape anything rendered through `innerHTML` with `esc()` from `util.js`.
- Colours and spacing come from the CSS custom properties in `:root`.

## Pull requests

Keep PRs small and focused, describe what you changed and why, and include a screenshot for visual changes (desktop and mobile).
