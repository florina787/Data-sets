import { Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Home from "./pages/Home";
import Overview from "./pages/Overview";
import Markets from "./pages/Markets";
import Stock from "./pages/Stock";
import Rankings from "./pages/Rankings";
import CrashRisk from "./pages/CrashRisk";
import Guardian from "./pages/Guardian";
import Lab from "./pages/Lab";
import Memory from "./pages/Memory";
import Models from "./pages/Models";
import Watchlist from "./pages/Watchlist";
import DataSettings from "./pages/DataSettings";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Home />} />
        <Route path="overview" element={<Overview />} />
        <Route path="markets" element={<Markets />} />
        <Route path="stock/:ticker" element={<Stock />} />
        <Route path="rankings" element={<Rankings />} />
        <Route path="risk" element={<CrashRisk />} />
        <Route path="guardian" element={<Guardian />} />
        <Route path="lab" element={<Lab />} />
        <Route path="memory" element={<Memory />} />
        <Route path="models" element={<Models />} />
        <Route path="watchlist" element={<Watchlist />} />
        <Route path="settings" element={<DataSettings />} />
        <Route path="*" element={<div className="content">Not found</div>} />
      </Route>
    </Routes>
  );
}
