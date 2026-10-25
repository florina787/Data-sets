# Security limitations (read this before showing the demo to a security team)

This is a **local demonstration**. It is **not** defense-accredited, not FedRAMP/CMMC/ITAR-assessed,
and not production secure. Specifically:

1. **Identity is simulated.** Anyone with access to the UI can pick any persona; there are no passwords or MFA. Production requires an enterprise IdP (OIDC/SAML), MFA, and real attribute sources for clearances.
2. **Tokens** are HMAC-signed with a per-install secret stored in the data directory. They are not revocable before expiry.
3. **The audit log is tamper-evident, not tamper-proof.** Anyone who can write the SQLite file can rewrite and re-hash the chain. Production needs WORM storage or external signing/anchoring.
4. **The egress guard is process-level.** It patches Python sockets in the backend process only; child processes (e.g. sandboxed adapter tests) and the browser are not covered. Use host/network firewalls.
5. **The adapter test sandbox is a subprocess**, not a container/VM/seccomp sandbox. It only ever runs code generated from repository templates.
6. **Prompt-injection detection is pattern-based.** The guarantee that matters is structural: retrieved text cannot trigger tools, exports or writes (POL-011), and agents never decide policy.
7. **Single SQLite file, no encryption at rest.** Fine for synthetic data; not for real controlled data.
8. **No real controlled, classified, export-controlled, customer, employee or aircraft data** may be loaded. The system has not been approved for such data, and compliance references are informational.
9. **The dev server has no CSP**; the production build adds a strict CSP meta tag. Security headers are set on all API responses.
10. **Dependencies** are pinned, but not vendored or SBOM-attested. Run your own vulnerability scanning.
