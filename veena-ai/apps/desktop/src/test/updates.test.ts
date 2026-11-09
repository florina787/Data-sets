import { describe, expect, it, vi } from "vitest";

vi.mock("electron", () => ({ net: { fetch: vi.fn() } }));
const { compareVersions, newestRelease } = await import("../../electron/updates");

const rel = (tag: string, extra: Partial<{ draft: boolean; prerelease: boolean; html_url: string }> = {}) => ({
  tag_name: tag,
  html_url: `https://github.com/florina787/Data-sets/releases/tag/${tag}`,
  body: `notes ${tag}`,
  draft: false,
  prerelease: false,
  ...extra,
});

describe("update check", () => {
  it("compares versions numerically, not as text", () => {
    expect(compareVersions("0.10.0", "0.9.9")).toBeGreaterThan(0);
    expect(compareVersions("1.0.0", "1.0.0")).toBe(0);
    expect(compareVersions("0.1.0", "0.1.1")).toBeLessThan(0);
  });

  it("picks the newest published VEENA release and ignores drafts, prereleases and other tags", () => {
    const best = newestRelease([
      rel("veena-ai-v0.2.0"),
      rel("veena-ai-v0.10.0", { draft: true }),
      rel("veena-ai-v0.9.0", { prerelease: true }),
      rel("other-v9.0.0"),
      rel("veena-ai-v0.3.1"),
    ]);
    expect(best?.version).toBe("0.3.1");
  });

  it("never offers a link outside the project's release pages", () => {
    expect(newestRelease([rel("veena-ai-v9.0.0", { html_url: "https://evil.example/download" })])).toBeNull();
  });
});
