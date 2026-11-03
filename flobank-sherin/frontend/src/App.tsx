import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import CommandCenter from "./pages/CommandCenter";
import Chat from "./pages/Chat";
import Portfolio from "./pages/Portfolio";
import Guardian from "./pages/Guardian";
import Harness from "./pages/Harness";
import { Azure, Python } from "./pages/Engineering";
import Tokens from "./pages/Tokens";
import Savings from "./pages/Savings";
import Metrics from "./pages/Metrics";
import Approvals from "./pages/Approvals";
import Esg from "./pages/Esg";
import Reports from "./pages/Reports";
import Settings from "./pages/Settings";
import { PageHeader } from "./components/ui";

export const ROUTES: [string, () => React.ReactElement][] = [
  ["/", CommandCenter], ["/chat", Chat], ["/portfolio", Portfolio], ["/guardian", Guardian], ["/harness", Harness], ["/azure", Azure], ["/python", Python],
  ["/tokens", Tokens], ["/savings", Savings], ["/metrics", Metrics], ["/approvals", Approvals], ["/esg", Esg], ["/reports", Reports], ["/settings", Settings],
];

export default function App() {
  return (
    <Layout>
      <Routes>
        {ROUTES.map(([p, C]) => <Route key={p} path={p} element={<C />} />)}
        <Route path="*" element={<PageHeader title="Page not found" subtitle="Use the navigation to return to the Financial Command Center." />} />
      </Routes>
    </Layout>
  );
}
