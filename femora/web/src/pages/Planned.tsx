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
        <p>This part of FEMORA Muse is being built (phase {n.milestone}). Nothing here is mocked up.</p>
        <p className="mt-2 text-muted">Meanwhile you can talk to Muse about it. Muse already helps with cycles, sleep, mood and preparing for appointments.</p>
        <Link to="/app/copilot"><Button variant="primary" className="mt-4">Talk to Muse</Button></Link>
      </Card>
    </div>
  );
}
