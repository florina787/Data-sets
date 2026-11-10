# Security policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems.

Report privately through GitHub's **[private vulnerability reporting](https://github.com/florina787/Data-sets/security/advisories/new)**. Include:
- what you found;
- the steps to reproduce it;
- the VEENA version (About page) and your operating system.

You will get an acknowledgement as soon as possible. Please allow time for a fix before disclosing publicly.

## Scope

- The VEENA.AI desktop app (Electron, the bundled backend, the managed AI runtime download), its installers and the CI release pipeline.
- The website in `site/`.

## How VEENA is protected

See [docs/SECURITY.md](docs/SECURITY.md) for the design (loopback-only backend with a per-launch token, isolated renderer, prompt-injection handling, secret masking) and [reports/SECURITY_AND_PRIVACY_AUDIT.md](reports/SECURITY_AND_PRIVACY_AUDIT.md) for the latest internal review.

That review is an internal engineering review. VEENA has **not** had an independent audit and claims no security certification.

## Known limitation

Beta installers are **not code-signed** yet. Download them only from this repository's Releases page and compare them with the published SHA-256 checksums.
