// Notify-only update check. VEENA never downloads or installs an update by
// itself: unsigned binaries must not be installed automatically, so the user
// is shown the release page and installs the new version like the first one.
import { net } from "electron";

export const RELEASES_API = "https://api.github.com/repos/florina787/Data-sets/releases?per_page=20";
export const RELEASE_TAG = /^veena-ai-v(\d+\.\d+\.\d+)$/;

export interface UpdateInfo {
  current: string;
  latest: string | null;
  newer: boolean;
  url: string | null;
  notes: string | null;
  error?: string;
}

/** Numeric semver comparison of x.y.z strings: >0 when a is newer than b. */
export function compareVersions(a: string, b: string): number {
  const pa = a.split(".").map(Number);
  const pb = b.split(".").map(Number);
  for (let i = 0; i < 3; i++) {
    if ((pa[i] ?? 0) !== (pb[i] ?? 0)) return (pa[i] ?? 0) - (pb[i] ?? 0);
  }
  return 0;
}

interface Release {
  tag_name: string;
  html_url: string;
  body: string | null;
  draft: boolean;
  prerelease: boolean;
}

/** The newest published (non-draft, non-prerelease) VEENA release in a list. */
export function newestRelease(releases: Release[]): { version: string; url: string; notes: string | null } | null {
  let best: { version: string; url: string; notes: string | null } | null = null;
  for (const r of releases) {
    const m = RELEASE_TAG.exec(r.tag_name);
    if (!m || r.draft || r.prerelease) continue;
    // Only release pages on GitHub are ever opened from here.
    if (!r.html_url.startsWith("https://github.com/florina787/Data-sets/releases/")) continue;
    if (!best || compareVersions(m[1], best.version) > 0) best = { version: m[1], url: r.html_url, notes: r.body };
  }
  return best;
}

export async function checkForUpdates(current: string): Promise<UpdateInfo> {
  try {
    // Sends no cookies or identifiers: one anonymous GET for public release metadata.
    const res = await net.fetch(RELEASES_API, { headers: { Accept: "application/vnd.github+json", "User-Agent": "VEENA.AI-update-check" } });
    if (!res.ok) return { current, latest: null, newer: false, url: null, notes: null, error: `HTTP ${res.status}` };
    const best = newestRelease((await res.json()) as Release[]);
    if (!best) return { current, latest: null, newer: false, url: null, notes: null };
    return { current, latest: best.version, newer: compareVersions(best.version, current) > 0, url: best.url, notes: (best.notes ?? "").slice(0, 2000) };
  } catch (e) {
    return { current, latest: null, newer: false, url: null, notes: null, error: (e as Error).message };
  }
}
