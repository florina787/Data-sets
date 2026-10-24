// The chat store against a SIMULATED backend stream (fetch is stubbed).
import { afterEach, describe, expect, it, vi } from "vitest";
import { Api } from "../services/api";
import { useApp } from "../stores/app";

function ndjsonResponse(events: object[]) {
  const body = new ReadableStream({
    start(c) {
      c.enqueue(new TextEncoder().encode(events.map((e) => JSON.stringify(e)).join("\n") + "\n"));
      c.close();
    },
  });
  return new Response(body, { status: 200, headers: { "content-type": "application/x-ndjson" } });
}

afterEach(() => vi.unstubAllGlobals());

describe("useApp.ask", () => {
  it("streams tokens, records metadata, then reloads persisted messages", async () => {
    const calls: string[] = [];
    vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => setTimeout(() => cb(0), 0));
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        calls.push(`${init?.method ?? "GET"} ${new URL(url).pathname}`);
        expect((init?.headers as Record<string, string>).Authorization).toBe("Bearer tok");
        if (url.endsWith("/api/chat"))
          return ndjsonResponse([
            { type: "accepted", request_id: "r1", user_message_id: 1 },
            { type: "meta", agent: "conversation", style: "quick", model: "m", vision: false, citations: [], notes: [], timings: {} },
            { type: "token", t: "Hello " },
            { type: "token", t: "world" },
            { type: "done", message_id: 2, stats: {}, total_ms: 5, governance: { flags: [], notes: [], cited: [], grounded: false }, cancelled: false },
          ]);
        if (url.includes("/api/sessions/s1")) return Response.json({ session: { id: "s1", mode: "conversation", title: "t" }, messages: [] });
        return Response.json([]);
      }),
    );
    useApp.setState({ api: new Api({ url: "http://127.0.0.1:1", token: "tok", status: "ready" }), currentSession: { id: "s1", mode: "conversation" } as never });
    const done = await useApp.getState().ask({ text: "hi" });
    expect(done?.message_id).toBe(2);
    expect(calls).toContain("POST /api/chat");
    expect(useApp.getState().live).toBeNull(); // persisted copy replaces the live answer
  });

  it("surfaces backend errors to the user", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) =>
        url.endsWith("/api/chat")
          ? ndjsonResponse([{ type: "error", code: "llm_unavailable", message: "Ollama is not reachable" }])
          : url.includes("/api/sessions/s1")
            ? Response.json({ session: { id: "s1", mode: "conversation", title: "t" }, messages: [] })
            : Response.json([]),
      ),
    );
    useApp.setState({ api: new Api({ url: "http://127.0.0.1:1", token: "tok", status: "ready" }), currentSession: { id: "s1", mode: "conversation" } as never });
    await useApp.getState().ask({ text: "hi" });
    expect(useApp.getState().live?.error).toContain("Ollama is not reachable");
  });
});
