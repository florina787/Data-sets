import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import App, { ROUTES } from "../App";
import { AppProvider } from "../lib/store";
import { SherinAvatar, SHERIN_IMAGE } from "../components/SherinAvatar";
import { NAV } from "../components/Layout";

beforeEach(() => { (globalThis as any).fetch = vi.fn(() => new Promise(() => {})); });

describe("Sherin's approved avatar", () => {
  it.each(ROUTES.map(([p]) => p))("route %s shows the same avatar asset in the shell and the page", (path) => {
    render(<MemoryRouter initialEntries={[path]}><AppProvider><App /></AppProvider></MemoryRouter>);
    const avatars = screen.getAllByTestId("sherin-avatar");
    expect(avatars.length).toBeGreaterThanOrEqual(2);
    expect(new Set(avatars.map((a) => a.getAttribute("data-src")))).toEqual(new Set([SHERIN_IMAGE]));
  });

  it("every navigation entry has a route", () => {
    expect(NAV.map((n) => n.to).sort()).toEqual(ROUTES.map(([p]) => p).sort());
    expect(ROUTES).toHaveLength(15);
  });

  it("uses one image file and falls back to a neutral monogram, never another face", () => {
    render(<SherinAvatar size="xl" />);
    const img = screen.getByAltText("Sherin, FLO Bank's AI");
    expect(img.getAttribute("src")).toBe(SHERIN_IMAGE);
    fireEvent.error(img);
    expect(screen.getByRole("img", { name: "Sherin (portrait pending)" })).toBeInTheDocument();
  });
});
