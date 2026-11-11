import { Link } from "react-router-dom";
import { useApp } from "../../context";
import { useNetwork } from "./geoData";

/** The shared geographic selection, visible on every page so context is never lost silently. */
export default function GeoChip() {
  const { geo } = useApp();
  if (!geo.country && !geo.node && !geo.incident) return null;
  return <Chip />;
}

function Chip() {
  const { geo, setGeo } = useApp();
  const { data } = useNetwork();
  const country = data?.countries.find((c) => c.id === geo.country)?.name ?? geo.country;
  const parts = [country, geo.node, geo.incident].filter(Boolean);
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-gold-500/50 bg-[#1a2433] px-2.5 py-1 text-xs text-gold-300" data-testid="geo-chip">
      <span aria-hidden>◎</span>
      <Link to="/" className="hover:underline" title="Geographic selection (shared across dashboards)">{parts.join(" › ")}</Link>
      <button className="ml-1 text-navy-600 hover:text-navy-900" onClick={() => setGeo({})} aria-label="Clear geographic selection">✕</button>
    </span>
  );
}
