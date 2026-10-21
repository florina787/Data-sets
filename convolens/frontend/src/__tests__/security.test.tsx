import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { safeCell, toCSV } from "../lib/csv";
import { Markdown } from "../lib/markdown";

describe("CSV export", () => {
  it("neutralises spreadsheet formulas but keeps numbers", () => {
    expect(safeCell("=HYPERLINK(\"x\")")).toBe("\"'=HYPERLINK(\"\"x\"\")\"");
    expect(safeCell("@SUM(A1)")).toBe("'@SUM(A1)");
    expect(safeCell("-12")).toBe("-12");
    expect(toCSV(["a"], [["+cmd"]])).toBe("a\r\n'+cmd");
  });
});

describe("Markdown renderer", () => {
  it("renders transcript HTML as inert text (no stored XSS)", () => {
    const { container } = render(<Markdown text={'**Finding**\n<img src=x onerror="alert(1)"> quote <script>alert(2)</script>'} />);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
    expect(container.textContent).toContain("<img src=x");
  });
  it("turns citations into buttons that report the reference", () => {
    const onCite = vi.fn();
    render(<Markdown text="12 of 40 unresolved [M1] see [E2]" onCite={onCite} />);
    screen.getByRole("button", { name: "Open evidence E2" }).click();
    expect(onCite).toHaveBeenCalledWith("E2");
    expect(screen.getByRole("button", { name: "Open metric M1" })).toBeInTheDocument();
  });
  it("splits grouped citations into individual buttons", () => {
    const { container } = render(<Markdown text="Customers report it [E1, E2, M3]." onCite={() => undefined} />);
    for (const name of ["Open evidence E1", "Open evidence E2", "Open metric M3"]) expect(within(container).getByRole("button", { name })).toBeInTheDocument();
  });
});
