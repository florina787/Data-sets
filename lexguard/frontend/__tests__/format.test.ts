import { describe, expect, it } from "vitest";
import { humanize, pct, splitHighlight, statusTone } from "@/lib/format";

describe("format helpers", () => {
  it("maps statuses to tones", () => {
    expect(statusTone("SUPPORTED")).toBe("good");
    expect(statusTone("PARTIALLY_SUPPORTED")).toBe("warn");
    expect(statusTone("ESCALATION_REQUIRED")).toBe("bad");
    expect(statusTone("ACCESS_DENIED")).toBe("bad");
    expect(statusTone("something-else")).toBe("neutral");
  });
  it("formats percentages and labels", () => {
    expect(pct(0.925)).toBe("93%");
    expect(pct(null)).toBe("-");
    expect(humanize("REVIEW_REQUIRED")).toBe("Review Required");
  });
  it("splits highlighted evidence case-insensitively", () => {
    expect(splitHighlight("The Supplier may terminate.", "may TERMINATE")).toEqual({ before: "The Supplier ", match: "may terminate", after: "." });
    expect(splitHighlight("abc", "zzz")).toEqual({ before: "abc", match: "", after: "" });
  });
});
