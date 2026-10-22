import { describe, expect, it, vi } from "vitest";
import { streamChat } from "@/services/api";
import type { StreamEvent } from "@/types/api";

function sseResponse(chunks: string[]) {
  const enc = new TextEncoder();
  const body = new ReadableStream({ start(c) { chunks.forEach((x) => c.enqueue(enc.encode(x))); c.close(); } });
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

describe("streamChat", () => {
  it("parses events split across network chunks", async () => {
    const a = `event: accepted\ndata: ${JSON.stringify({ type: "accepted", request_id: "R1" })}\n\n`;
    const b = `event: node_start\ndata: ${JSON.stringify({ type: "node_start", node: "intent" })}\n\n`;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sseResponse([a.slice(0, 20), a.slice(20) + b.slice(0, 10), b.slice(10)])));
    const events: StreamEvent[] = [];
    await new Promise<void>((resolve) => {
      streamChat({ question: "q" }, (e) => { events.push(e); if (events.length === 2) resolve(); }, () => resolve());
    });
    expect(events.map((e) => e.type)).toEqual(["accepted", "node_start"]);
    vi.unstubAllGlobals();
  });

  it("reports HTTP errors with the server's detail", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Question too long" }), { status: 422 })));
    const err = await new Promise<Error>((resolve) => streamChat({ question: "q" }, () => {}, resolve));
    expect(err.message).toBe("Question too long");
    vi.unstubAllGlobals();
  });
});
