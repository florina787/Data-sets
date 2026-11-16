import { Link } from "react-router-dom";
import { NAV } from "../modules/navigation";
import { Button, Card, PageHeader } from "../components/ui";

/** Honest placeholder for modules scheduled in later milestones. Navigation works; nothing is faked. */
export function Planned({ path }: { path: string }) {
  const n = NAV.find((x) => x.path === path)!;
  return (
    <div>
      <PageHeader title={n.label} status="planned" sub={n.summary} />
      <Card>
        <p>This module is scheduled for <b>Milestone {n.milestone}</b> of the leadership-demo plan. It isn't built yet, and the demo doesn't pretend otherwise.</p>
        <p className="mt-2 text-muted">You can ask FEMORA about this topic in the meantime. The copilot already handles cycle, sleep, mood and doctor-preparation conversations.</p>
        <Link to="/app/copilot"><Button variant="primary" className="mt-4">Talk to FEMORA</Button></Link>
      </Card>
    </div>
  );
}
