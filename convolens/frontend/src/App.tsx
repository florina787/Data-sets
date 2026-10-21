import { Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { AppProvider } from "./lib/state";
import { Overview } from "./pages/Overview";
import { AskFlo } from "./pages/AskFlo";
import { Explorer } from "./pages/Explorer";
import { InsightMaps } from "./pages/InsightMaps";
import { Opportunities } from "./pages/Opportunities";
import { Decisions } from "./pages/Decisions";
import { Impact } from "./pages/Impact";
import { DataQuality } from "./pages/DataQuality";
import { Observability } from "./pages/Observability";
import { Languages } from "./pages/Languages";
import { Review } from "./pages/Review";

export function App() {
  return (
    <AppProvider>
      <Layout>
        <Routes>
          <Route path="/" element={<Overview />} />
          <Route path="/ask" element={<AskFlo />} />
          <Route path="/explorer" element={<Explorer />} />
          <Route path="/maps" element={<InsightMaps />} />
          <Route path="/opportunities" element={<Opportunities />} />
          <Route path="/decisions" element={<Decisions />} />
          <Route path="/impact" element={<Impact />} />
          <Route path="/review" element={<Review />} />
          <Route path="/languages" element={<Languages />} />
          <Route path="/quality" element={<DataQuality />} />
          <Route path="/observability" element={<Observability />} />
          <Route path="*" element={<p className="text-sm text-muted">Page not found.</p>} />
        </Routes>
      </Layout>
    </AppProvider>
  );
}
