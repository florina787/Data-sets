# Deployment and offline installation

## Local (recommended for the demo)
See README quick start. Defaults: `DEMO_MODE=true`, `OFFLINE_MODE=true`, `LLM_ENABLED=false`. Data in `backend/data/` (git-ignored).

## Offline installation strategy
1. On a connected machine with the same OS/arch:
   ```bash
   cd flying-florina/backend && python3 -m venv .venv && .venv/bin/pip download -r requirements.txt -d ../offline/wheels
   cd ../frontend && npm ci && tar czf ../offline/node_modules.tgz node_modules
   ```
2. Copy the repository and `offline/` to the target machine.
3. Install without network:
   ```bash
   cd flying-florina/backend && python3 -m venv .venv && .venv/bin/pip install --no-index --find-links ../offline/wheels -r requirements.txt
   cd ../frontend && tar xzf ../offline/node_modules.tgz
   ```
4. `make demo` (or the two commands in the README). Verify with `make offline` and `make smoke`.

For Playwright, download the browser once (`npx playwright install chromium`) and copy `~/.cache/ms-playwright`.

## Docker (optional)
```bash
docker compose build            # while connected
docker save -o ff-images.tar flying-florina-backend flying-florina-frontend
docker load -i ff-images.tar    # on the offline host
docker compose up               # UI http://127.0.0.1:4173, API :8000
```
Ports are bound to 127.0.0.1. Images were not built in CI for this release.

## Optional local LLM
Install Ollama or llama.cpp yourself, download a model whose license you accept, then set `LLM_ENABLED=true`
and `LLM_URL=http://127.0.0.1:11434`. Non-loopback URLs are denied (POL-008). The current release only detects
and reports the model; it does not use it for answers or decisions.

## Production (out of scope)
Enterprise IdP + MFA, managed PostgreSQL with encryption, WORM/externally anchored audit, container sandboxing for
generated-code tests, reverse proxy with rate limiting/WAF, secrets manager, SBOM and vulnerability scanning,
and a formal security and compliance assessment. See SECURITY_LIMITATIONS.md.
