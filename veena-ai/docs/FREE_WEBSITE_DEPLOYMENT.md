# Deploying the VEENA.AI website for free

The site is static HTML in [`veena-ai/site/`](../site): espresso-brown, dark by default with a light toggle, mobile-responsive, with no cookies and no analytics. It is hosted on **GitHub Pages** at `https://florina787.github.io/Data-sets/`.

## What is already done (in the repository)

- `site/index.html`: product overview, real screenshots, features, download buttons, install steps, privacy summary, requirements, model licences, known limitations, support.
- `site/privacy.html`: privacy policy.
- `site/downloads.js`: enables a download button **only** when GitHub's public API confirms the file exists in the newest published `veena-ai-v*` release. Until then the buttons show "Coming soon" and link nowhere.
- `site/build.sh`: copies the site and the screenshots it uses into `_site`, fills in repository links for the deployed branch, refuses to publish any file named like the private founder photo, and checks that every local link resolves.
- `.github/workflows/veena-ai-site.yml`: builds and checks the site on every change, including on a phone-sized screen and that every enabled download link answers. It deploys only when run by hand with **deploy** ticked.

## One-time setup by the owner (about 2 minutes)

1. Merge the VEENA.AI branch into the default branch (so repository links in the site resolve).
2. GitHub → **Settings → Pages → Build and deployment → Source: GitHub Actions**.
3. GitHub → **Actions → VEENA.AI website → Run workflow**, tick **deploy**, run.
4. The deploy job prints the live URL and checks that it responds.

No account, card or domain is needed. HTTPS is provided automatically on `github.io`.

## Rollback

Run **VEENA.AI website** again from an earlier commit or tag (the *Use workflow from* selector), with **deploy** ticked. Pages serves whichever build was deployed last.

## Test locally

```bash
REF=main veena-ai/site/build.sh /tmp/veena-site
python3 -m http.server 8765 -d /tmp/veena-site   # open http://127.0.0.1:8765
```

## Optional later

- **Custom domain:** not purchased; Pages supports one with free HTTPS if the owner buys a domain.
- **Fallback host:** Cloudflare Pages (static requests free and unlimited) can serve the same `_site` folder if traffic passes the Pages 100 GB soft limit.
