import { Page } from "@playwright/test";

// Flo & Jerry 3.0 navigation: 7 sections, only the active one expanded. Opens the section
// that holds a page, then clicks the page link (same link names as before 3.0).
const SECTION_OF: Record<string, string> = {
  "Enterprise Pulse": "Overview", "Executive Command": "Overview", "Priorities & decisions": "My Priorities",
  "Quality Intelligence": "Operations", "Potato Inspection": "Operations", Inventory: "Operations",
  "Sales & Promotions": "Operations", "Compliance & Food Safety": "Operations", "Supply-chain globe": "Global Network",
  "Ask Copilot": "Jerry AI", "Technology health": "Technology", "System Observability": "Technology",
  "Model Evaluation Lab": "Technology", "Agent Intelligence": "Technology", "Delivery overview": "Technology",
  "Brief intake": "Technology", "Delivery board": "Technology", Requirements: "Technology", Engineering: "Technology",
  Quality: "Technology", "Release center": "Technology", Incidents: "Technology", "Scenario templates": "Technology",
  "Weekly CTO review": "Reports", "Evidence & audit": "Reports", "Export Studio": "Reports",
  "Guided CTO demo": "Overview", "Team & delivery portfolio": "Operations", "Defense Command": "Technology",
  "Connect your enterprise": "Technology",
};

export async function navTo(page: Page, label: string) {
  const nav = page.getByRole("navigation", { name: "Primary" });
  const link = nav.getByRole("link", { name: label, exact: true });
  if (!(await link.isVisible())) {
    const section = nav.getByRole("button", { name: SECTION_OF[label] });
    if ((await section.getAttribute("aria-expanded")) !== "true") await section.click();
  }
  await link.click();
}
