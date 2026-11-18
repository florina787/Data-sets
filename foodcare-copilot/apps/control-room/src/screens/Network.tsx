import { lazy, Suspense } from "react";
import { Skeleton } from "../components/pulse/shared";

const SupplyMap = lazy(() => import("../components/geo/SupplyMap"));

/** Global Network workspace: the shared supply-chain map, full width. */
export default function Network() {
  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <header>
        <div className="eyebrow">Global network</div>
        <h1 className="mt-1 text-3xl font-semibold tracking-tight text-ink">Supply-chain globe</h1>
        <p className="mt-1 text-ink-muted">Explore countries, sites, routes and quality incidents; trace any site back to the farm with OriginTrace. The network is a labelled synthetic scenario.</p>
      </header>
      <Suspense fallback={<div className="panel"><Skeleton lines={8} /></div>}>
        <SupplyMap title="Global supply chain intelligence" defaultTab="forecast" defaultOverlay="exposure" />
      </Suspense>
    </div>
  );
}
