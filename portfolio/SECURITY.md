# Security Policy

## Scope

This repository is a static portfolio site. It has **no backend, no database, no authentication and no API keys**. Every interactive demo (the agent workflow, RAG explorer, MCP tool lab and telemetry dashboard) is a local simulation that runs in the visitor's browser over synthetic data.

## Reporting a vulnerability

If you find a security issue, for example an XSS vector in the terminal, command palette or RAG input, or a committed secret:

1. **Do not open a public issue.**
2. Report it privately through GitHub's **"Report a vulnerability"** button (Security → Advisories), or email the address listed in the site's Contact section.
3. Include steps to reproduce, the affected file and the browser you used.

You can expect an acknowledgement within 5 business days.

## Safeguards in this repository

- **No secrets.** `scripts/check.mjs` scans every text file for credential-like values (`sk-…`, `*_API_KEY=…`, AWS keys, GitHub tokens, private keys). The deploy workflow runs it and fails if anything matches.
- **No arbitrary execution.** The terminal matches input against a fixed command table. There is no `eval`, `Function` or shell.
- **Output encoding.** All user input and data rendered with `innerHTML` is HTML-escaped first.
- **No third-party scripts by default.** Analytics are disabled unless explicitly enabled in `assets/js/config.js`, and even then they respect Do Not Track / Global Privacy Control.
- **Least-privilege CI.** The Pages workflow only requests `contents: read`, `pages: write` and `id-token: write`.
