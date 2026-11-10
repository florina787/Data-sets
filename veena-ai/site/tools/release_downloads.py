"""Download totals for published VEENA releases, from GitHub's own per-file counters.

    python site/tools/release_downloads.py            # table
    python site/tools/release_downloads.py --json     # machine-readable

What the number means: GitHub counts each completed request for a release file
(`download_count`). It is a count of file downloads, NOT of people and NOT of
installs: one person can download twice, a download can be abandoned, and CI or
mirrors count too. Drafts are skipped (their files are private). No token is
needed for a public repository; set GITHUB_TOKEN only to raise the rate limit.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

REPO = "florina787/Data-sets"
PREFIX = "veena-ai-v"
PLATFORM = {".exe": "Windows", ".dmg": "macOS", ".AppImage": "Linux"}


def fetch(url: str) -> list[dict]:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "veena-release-stats"}
    if os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:  # noqa: S310 - fixed https URL
        return json.load(r)


def main() -> int:
    releases = [
        r
        for r in fetch(f"https://api.github.com/repos/{REPO}/releases?per_page=100")
        if r.get("tag_name", "").startswith(PREFIX) and not r.get("draft")
    ]
    rows = []
    for rel in releases:
        for a in rel.get("assets", []):
            plat = next((p for ext, p in PLATFORM.items() if a["name"].endswith(ext)), None)
            if plat:
                rows.append(
                    {
                        "release": rel["tag_name"],
                        "published": (rel.get("published_at") or "")[:10],
                        "platform": plat,
                        "file": a["name"],
                        "downloads": a["download_count"],
                    }
                )
    if "--json" in sys.argv:
        print(json.dumps(rows, indent=2))
        return 0
    if not rows:
        print("No published VEENA release yet: there are no download counts to report.")
        return 0
    print(f"{'release':18} {'published':11} {'platform':9} {'downloads':>9}  file")
    for r in rows:
        print(f"{r['release']:18} {r['published']:11} {r['platform']:9} {r['downloads']:>9}  {r['file']}")
    print(f"\nTotal installer downloads: {sum(r['downloads'] for r in rows)} (file downloads, not people or installs)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
