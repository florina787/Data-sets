import { api } from "../lib/api";
import { useApi } from "../lib/useApi";
import { num, pct, tone } from "../lib/format";
import { ErrorBox, Loading, Panel, StatusBadge, SyntheticNotice } from "../components/ui";
import { Sparkline } from "../components/charts";

export default function Markets() {
  const { data, error } = useApi(() => api.overview());
  if (error) return <div className="content"><ErrorBox error={error} /></div>;
  if (!data) return <div className="content"><Loading /></div>;
  const block = (title: string, tiles: typeof data.sectors) => (
    <Panel title={title} right={<StatusBadge status={data.data_status} />}>
      <table className="t">
        <thead><tr><th>Composite</th><th className="r">Level</th><th className="r">1d</th><th className="r">30 sessions</th></tr></thead>
        <tbody>{tiles.map((t) => (
          <tr key={t.name}><td>{t.name}</td><td className="r num">{num(t.value)}</td>
            <td className={`r num ${tone(t.change_1d)}`}>{pct(t.change_1d)}</td><td className="r"><Sparkline values={t.spark} /></td></tr>
        ))}</tbody>
      </table>
    </Panel>
  );
  return (
    <div className="content grid">
      <SyntheticNotice status={data.data_status} />
      <div className="grid g2">{block("Sectors", data.sectors)}{block("Countries", data.countries)}</div>
      <p className="faint" style={{ fontSize: 12 }}>
        Composites are equal-weighted from point-in-time constituents, including names that later delisted. Bonds, FX and
        commodities are not ingested yet (see DATA_PROVIDER_MATRIX.md).
      </p>
    </div>
  );
}
