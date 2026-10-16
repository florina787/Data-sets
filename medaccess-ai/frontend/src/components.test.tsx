import { render, screen } from "@testing-library/react";

import { LangGraphVisualizer } from "./components/agents";
import { ChristinaAvatar } from "./components/ChristinaAvatar";
import { AppointmentCard } from "./components/search";
import { AvailabilityBadge } from "./components/ui";
import { NAV, visibleNav } from "./layouts/AppLayout";
import type { Recommendation, TraceEntry } from "./services/api";

const rec = (over: Partial<Recommendation> = {}): Recommendation => ({
  rank: 1, tier: "CONFIRMED_ALTERNATIVE", facility_id: "FAC-003", facility_name: "Northgate MRI & CT Clinic (Demo)",
  slot_id: "S1", service: "MRI", start_local: "2026-10-21T08:00-04:00", days_until: 5, days_saved: 85, straight_km: 14,
  est_driving_minutes: 34, verification_status: "VERIFIED_AVAILABLE", display_status: "DEMO_SIMULATED",
  eligibility_status: "ELIGIBLE", reasons: [], source_id: "INT-SYN-NORTH", last_verified_at: null, is_synthetic: true,
  booking_capability: "online_handoff", ...over,
});

describe("navigation", () => {
  it("has all 35 items", () => {
    expect(NAV.flatMap((s) => s.items)).toHaveLength(35);
  });
  it("hides engineering and admin pages from patients", () => {
    const labels = visibleNav("patient").flatMap((s) => s.items.map((i) => i.label));
    expect(labels).toContain("Ask Christina");
    expect(labels).not.toContain("AI-SDLC Command Center");
    expect(labels).not.toContain("Administration");
    expect(visibleNav("admin").flatMap((s) => s.items)).toHaveLength(35);
    expect(visibleNav("engineer").flatMap((s) => s.items.map((i) => i.label))).not.toContain("Administration");
  });
});

describe("components", () => {
  it("labels Christina as a virtual assistant", () => {
    render(<ChristinaAvatar state="warning" />);
    expect(screen.getByRole("img", { name: /virtual AI assistant.*safety/ })).toBeInTheDocument();
  });
  it("shows demo marker on synthetic availability", () => {
    render(<AvailabilityBadge status="VERIFIED_AVAILABLE" simulated />);
    expect(screen.getByText("DEMO_SIMULATED")).toBeInTheDocument();
  });
  it("marks unverified possibilities as not confirmed", () => {
    render(<AppointmentCard rec={rec({ tier: "UNVERIFIED_POSSIBILITY", verification_status: "ADVERTISED_UNVERIFIED" })} />);
    expect(screen.getByText(/NOT CONFIRMED/)).toBeInTheDocument();
    expect(screen.getByText(/Unverified possibility/)).toBeInTheDocument();
  });
  it("shows days saved only for verified alternatives", () => {
    render(<AppointmentCard rec={rec()} />);
    expect(screen.getByText("85 days sooner")).toBeInTheDocument();
  });
  it("renders workflow states without animation when reduced motion is on", () => {
    const trace: TraceEntry[] = [
      { node: "intake", agent: "intake", title: "Patient Intake Agent", status: "completed", action: "ok", duration_ms: 1, at: "" },
      { node: "human_approval", agent: "human_approval", title: "Human Approval Agent", status: "awaiting_approval", action: "wait", duration_ms: 0, at: "" },
    ];
    render(<LangGraphVisualizer trace={trace} reducedMotion />);
    expect(screen.getByText("Human Approval")).toBeInTheDocument();
    expect(screen.getByText(/awaiting approval/)).toBeInTheDocument();
  });
});
