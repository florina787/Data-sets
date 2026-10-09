import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "@/lib/api";

afterEach(() => vi.restoreAllMocks());

describe("api client", () => {
  it("sends the identity header and parses JSON", async () => {
    const f = vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify([{ matter_id: "M-1001" }]), { status: 200 }));
    const r = await api.matters("U-002");
    expect(r[0].matter_id).toBe("M-1001");
    expect((f.mock.calls[0][1] as RequestInit).headers).toMatchObject({ "X-LexGuard-User": "U-002" });
  });
  it("raises structured ApiError with backend code", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify({ detail: { code: "ETHICAL_WALL", message: "Screened." } }), { status: 403 }));
    await expect(api.matter("U-003", "M-1003")).rejects.toMatchObject({ status: 403, code: "ETHICAL_WALL", message: "Screened." });
  });
  it("reports an unreachable backend clearly", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("fetch failed"));
    await expect(api.health()).rejects.toBeInstanceOf(ApiError);
  });
});
