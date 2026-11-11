import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import Overview from "./pages/Overview";
import Topology from "./pages/Topology";
import RCA from "./pages/RCA";
import Actions from "./pages/Actions";
import Integrations from "./pages/Integrations";
import Sources from "./pages/Sources";
import Governance from "./pages/Governance";
import FinOps from "./pages/FinOps";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Overview />} />
        <Route path="topology" element={<Topology />} />
        <Route path="rca" element={<RCA />} />
        <Route path="actions" element={<Actions />} />
        <Route path="integrations" element={<Integrations />} />
        <Route path="sources" element={<Sources />} />
        <Route path="governance" element={<Governance />} />
        <Route path="finops" element={<FinOps />} />
      </Route>
    </Routes>
  );
}
