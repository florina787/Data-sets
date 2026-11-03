import { render, screen } from "@testing-library/react";
import { money, compact, pctChange, wrap, lastMonths } from "../lib/format";
import { Markdown } from "../components/ui";
import { chatStream } from "../lib/api";

describe("format", () => {
  it("formats money in USD, INR and CAD", () => {
    expect(money(40280576.68, "USD")).toBe("$40.28M");
    expect(money(93544.2, "INR")).toBe("₹93.5K");
    expect(money(-7357.96, "CAD")).toBe("−C$7,357.96");
    expect(money(1234.5, "USD", false)).toBe("$1,234.50");
    expect(money(null)).toBe("—");
  });
  it("other helpers", () => {
    expect(compact(117358473)).toBe("117.4M");
    expect(pctChange(2.34)).toBe("+2.3%");
    expect(wrap("Human-equivalent value of verified work", 16)).toContain("<br>");
    expect(lastMonths("2026-01", 3)).toEqual(["2026-01", "2025-12", "2025-11"]);
  });
});

describe("Markdown", () => {
  it("renders bold, lists and italics", () => {
    render(<Markdown text={"**Net** benefit\n\n- one\n- two\n\n_note_"} />);
    expect(screen.getByText("Net").tagName).toBe("STRONG");
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
    expect(screen.getByText("note").tagName).toBe("EM");
  });
  it("never injects HTML", () => {
    const { container } = render(<Markdown text={'<img src=x onerror="alert(1)">'} />);
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("<img");
  });
});

describe("chatStream", () => {
  it("parses SSE events split across chunks", async () => {
    const parts = ['event: activity\ndata: {"step":1,"tool":"intent.detect"}\n\nevent: del', 'ta\ndata: "Hello "\n\nevent: delta\ndata: "world"\n\n',
      'event: final\ndata: {"text":"Hello world","intent":"x"}\n\nevent: done\ndata: {}\n\n'];
    const enc = new TextEncoder();
    let i = 0;
    (globalThis as any).fetch = vi.fn(async () => ({ ok: true, body: { getReader: () => ({ read: async () => (i < parts.length ? { value: enc.encode(parts[i++]), done: false } : { value: undefined, done: true }) }) } }));
    const acts: any[] = []; let text = ""; let fin: any = null;
    await chatStream({ message: "hi" }, { activity: (a) => acts.push(a), delta: (d) => (text += d), final: (p) => (fin = p) });
    expect(acts).toHaveLength(1);
    expect(text).toBe("Hello world");
    expect(fin.intent).toBe("x");
  });
});
