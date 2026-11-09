# Installer storage and delivery

## Where installers live

**GitHub Releases** of `florina787/Data-sets`, tag `veena-ai-v<version>`:

| File | Platform | Measured size |
|---|---|---|
| `VEENA.AI-Windows-Setup.exe` | Windows 10/11 x64 (NSIS, per-user, desktop + Start menu shortcuts, uninstaller) | 487 MB |
| `VEENA.AI-macOS-AppleSilicon.dmg` | macOS on Apple Silicon | not yet measured |
| `VEENA.AI-Linux-x86_64.AppImage` | Linux x86_64 | 740 MB |
| `SHA256SUMS.txt` | checksums of the three files | |

Releases allow files up to 2 GiB and state no bandwidth or total-size limit. Installers are never stored in a database, in Actions artifacts for customers (those expire and require a login), or in the website.

## How a release is made

1. Push to the branch: CI builds all three installers, **installs them** (Windows silent install, macOS disk image, Linux AppImage), launches the installed app, runs the **first-run test** (downloads the real AI runtime, downloads a small model, requires a real answer and a cited document answer), uninstalls, and records SHA-256 checksums and signature status.
2. Owner runs **Actions → VEENA.AI CI → Run workflow** with **create_draft_release** ticked. After all builds and the security job pass, the `draft-release` job (environment `release`, which can require the owner's approval) creates a **draft** release with the installers and `SHA256SUMS.txt`.
3. Owner reviews the draft on GitHub and presses **Publish release**. Only then are the files public.
4. The website's buttons enable themselves on the next page load, because the files now exist.

Safety rules built into the workflow:

- A published release is **never overwritten**. Re-running for a published version fails; bump `version` in `apps/desktop/package.json` instead.
- Each OS uses only its own signing certificate.
- Nothing is published automatically.

## Integrity and signing

- **Checksums:** SHA-256 for every installer in the CI summary, the release notes and `SHA256SUMS.txt`.
- **SBOM:** CycloneDX bills of materials for the Python and npm dependencies (CI artifact `veena-ai-sbom-and-licences`).
- **Code signing:** prepared but **not active**. It needs certificates the project does not have:
  - Windows: an Authenticode certificate → secrets `WIN_CSC_LINK` (base64 .pfx) and `WIN_CSC_KEY_PASSWORD`.
  - macOS: Apple Developer Program membership (US$99/year) → Developer ID Application certificate as `MAC_CSC_LINK`/`MAC_CSC_KEY_PASSWORD`, and `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, `APPLE_TEAM_ID` for notarization.
  - Until then, the CI summary reports the installers as unsigned, and Windows SmartScreen and macOS Gatekeeper warn on first launch.

## Bandwidth

See [reports/FREE_TIER_COST_SIMULATION.md](../reports/FREE_TIER_COST_SIMULATION.md): about 62 GB, 620 GB and 6.2 TB a month for 100, 1,000 and 10,000 downloads, all on GitHub Releases at $0.
