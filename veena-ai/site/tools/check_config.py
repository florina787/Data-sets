"""Checks site/config.js before the website is built, so nothing is switched on unverified.

    python site/tools/check_config.py site/config.js

- discussionsEnabled may be true only if GitHub reports Discussions enabled on the repository.
- formUrl, if set, must be a public Google Forms /viewform link with entry.<n> IDs.
- cloudflareToken, if set, must look like a Cloudflare Web Analytics site token.
- No value may look like a secret (API keys, SMTP passwords, private tokens).
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request

REPO = "florina787/Data-sets"


def parse(path: str) -> dict:
    src = open(path, encoding="utf-8").read()
    body = src[src.index("window.VEENA_CONFIG = ") + len("window.VEENA_CONFIG = ") : src.rindex(";")]
    body = re.sub(r"(?m)^\s*//[^\n]*", "", body)  # whole-line comments (URLs keep their //)
    body = re.sub(r"([{,]\s*)([A-Za-z_]\w*)\s*:", r'\1"\2":', body)  # bare keys
    body = re.sub(r",(\s*[}\]])", r"\1", body)  # trailing commas
    return json.loads(body), src


def main() -> int:
    cfg, src = parse(sys.argv[1])
    problems = []
    for pat, what in [
        (r"AKIA[0-9A-Z]{16}", "AWS key"),
        (r"gh[pousr]_[A-Za-z0-9]{30,}", "GitHub token"),
        (r"(?i)(smtp|password|passwd|secret|api[_-]?key)\s*[:=]\s*[\"'][^\"']+", "credential"),
        (r"AIza[0-9A-Za-z_-]{35}", "Google API key"),
        (r"xox[baprs]-", "Slack token"),
    ]:
        if re.search(pat, src):
            problems.append(f"config.js contains something that looks like a {what}; secrets never go in website JavaScript")

    fb = cfg.get("feedback") or {}
    if fb.get("formUrl") is not None:
        if not re.fullmatch(r"https://docs\.google\.com/forms/d/e/[A-Za-z0-9_-]{20,}/viewform", fb["formUrl"]):
            problems.append("feedback.formUrl must be the form's public link ending in /viewform")
        for k in ("experience", "type", "message"):
            if not re.fullmatch(r"entry\.\d+", str((fb.get("entries") or {}).get(k))):
                problems.append(f"feedback.entries.{k} must be an entry.<number> ID from the pre-filled link")

    ins = cfg.get("insightsUrl")
    if ins is not None and not re.fullmatch(r"https://[A-Za-z0-9.-]+(/[A-Za-z0-9._-]*)*", str(ins)):
        problems.append("insightsUrl must be the https:// URL of the deployed VEENA Insights Worker")

    token = cfg.get("cloudflareToken")
    if token is not None and not re.fullmatch(r"[a-f0-9]{32}", str(token)):
        problems.append("cloudflareToken must be the 32-character site token from Cloudflare Web Analytics")

    if cfg.get("discussionsEnabled") is True:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{REPO}", headers={"Accept": "application/vnd.github+json", "User-Agent": "veena-site-check"}
        )
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 - fixed https URL
            if not json.load(r).get("has_discussions"):
                problems.append("discussionsEnabled is true but Discussions is not enabled on the repository")

    for p in problems:
        print("FAIL:", p)
    if not problems:
        state = {
            "feedback form": "on" if fb.get("formUrl") else "pending (no form yet)",
            "community link": "on" if cfg.get("discussionsEnabled") else "hidden (Discussions not enabled)",
            "visitor analytics": "on" if token else "off",
        }
        print("config OK: " + "; ".join(f"{k}: {v}" for k, v in state.items()))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
