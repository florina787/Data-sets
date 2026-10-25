import { fmt, miniMarkdown } from "@/lib/format";
import { buildOption } from "@/components/Chart";

describe("miniMarkdown", () => {
  it("escapes HTML before formatting (XSS safe)", () => {
    const html = miniMarkdown('<img src=x onerror="alert(1)"> **bold**');
    expect(html).not.toContain("<img");
    expect(html).toContain("&lt;img");
    expect(html).toContain("<strong>bold</strong>");
  });
  it("renders lists", () => {
    expect(miniMarkdown("- a\n- b")).toBe("<ul><li>a</li><li>b</li></ul>");
  });
});

describe("fmt", () => {
  it("formats values", () => {
    expect(fmt(null)).toBe("-");
    expect(fmt(true)).toBe("Yes");
    expect(fmt([1, 2])).toBe("1, 2");
  });
});

describe("buildOption", () => {
  it("keeps chart data exactly as given and adds the demo threshold line", () => {
    const opt = buildOption({ kind: "line", x: ["d1", "d2"], series: [{ name: "v", data: [0.5, null] }], markLine: { y: 1, label: "Demo threshold" } }, false) as {
      series: { data: unknown[]; markLine?: { data: { yAxis: number }[] } }[];
    };
    expect(opt.series[0].data).toEqual([0.5, null]);
    expect(opt.series[0].markLine?.data[0].yAxis).toBe(1);
  });
  it("builds pie data from x and first series", () => {
    const opt = buildOption({ kind: "pie", x: ["a", "b"], series: [{ name: "n", data: [3, 4] }] }, true) as { series: { data: { name: string; value: number }[] }[] };
    expect(opt.series[0].data).toEqual([{ name: "a", value: 3 }, { name: "b", value: 4 }]);
  });
});
