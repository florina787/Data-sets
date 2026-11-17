import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { AppStateProvider } from "../lib/app-state";
import { AppRoutes } from "../App";

const seedLocation = () => localStorage.setItem("femora:v1:locations", JSON.stringify({ bea: { region: "North America", city: "Austin" }, nancy: { region: "North America", city: "Nashville" } }));
const at = (path: string) => { seedLocation(); return render(<AppStateProvider><MemoryRouter initialEntries={[path]}><AppRoutes /></MemoryRouter></AppStateProvider>); };

describe("app", () => {
  it("shows the Muse homepage with its main action and the creator credit", () => {
    at("/");
    expect(screen.getAllByText(/Meet your Muse/).length).toBeGreaterThan(0);
    expect(screen.getByText("florinaregius@yahoo.com")).toBeInTheDocument();
  });

  it("navigates every module without crashing", async () => {
    for (const p of ["/app", "/app/copilot", "/app/food", "/app/joy", "/app/settings", "/app/free-care", "/app/reminders", "/app/medscan", "/app/connections", "/app/journey", "/app/sisterhood", "/app/care", "/app/guardian", "/app/body"]) {
      const { unmount } = at(p);
      expect(await screen.findByText("florinaregius@yahoo.com")).toBeInTheDocument();
      await screen.findByRole("heading", { level: 1 }, { timeout: 3000 });
      expect(screen.queryByText(/fictional|simulat/i)).toBeNull();
      unmount();
    }
  }, 30000);

  it("holds a multi-message conversation", async () => {
    const u = userEvent.setup();
    at("/app/copilot");
    const box = await screen.findByLabelText("Message Muse", {}, { timeout: 3000 });
    await u.type(box, "I've been sleeping badly{Enter}");
    expect(await screen.findByText(/Poor sleep wears everything down/)).toBeInTheDocument();
    await u.type(box, "and I feel lonely{Enter}");
    expect(await screen.findByText(/That sounds hard/)).toBeInTheDocument();
    expect(screen.getAllByText("I've been sleeping badly").length).toBeGreaterThan(0);
  });

  it("logs food in plain language and updates nutrients", async () => {
    const u = userEvent.setup();
    at("/app/food");
    await u.type(await screen.findByLabelText("Describe your meal", {}, { timeout: 3000 }), "dal and curd for lunch{Enter}");
    expect(await screen.findByText(/Added Dal \(lentils\) ×1, Curd \/ dahi ×1 to Lunch/)).toBeInTheDocument();
    const lunch = screen.getByLabelText("Servings of Dal (lentils)");
    expect(lunch).toHaveValue(1);
    expect(within(document.body).getByText(/kcal · 2 items$/)).toBeInTheDocument();
  });

  it("Bea is an example configuration with no assumed health details", async () => {
    at("/app/settings");
    expect(await screen.findByLabelText("Name", {}, { timeout: 3000 })).toHaveValue("Bea");
    expect(screen.getByDisplayValue("37")).toBeInTheDocument();
    expect((screen.getByLabelText(/Life stage/) as HTMLSelectElement).value).toBe("");
  });

  it("Discover shows verified sources and never invents events", async () => {
    globalThis.fetch = (async () => new Response(JSON.stringify({ items: [] }))) as typeof fetch;
    at("/app/free-care");
    expect(await screen.findByText(/No verified events for Austin yet/, {}, { timeout: 3000 })).toBeInTheDocument();
    expect(screen.getByText("Cervical cancer screening recommendation")).toBeInTheDocument();
  });
});

describe("onboarding", () => {
  it("asks for region and city on first visit", () => {
    render(<AppStateProvider><MemoryRouter initialEntries={["/app"]}><AppRoutes /></MemoryRouter></AppStateProvider>);
    expect(screen.getByRole("dialog", { name: /Where are you, Bea/ })).toBeInTheDocument();
    expect(screen.getByLabelText("Region")).toBeInTheDocument();
    expect(screen.getByLabelText(/City/)).toBeInTheDocument();
  });
});
