import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppStateProvider } from "./lib/app-state";
import { AppShell } from "./components/AppShell";
import { Showcase } from "./pages/Showcase";
import { Home } from "./pages/Home";
import { Joy } from "./pages/Joy";
import { Settings } from "./pages/Settings";
import { Planned } from "./pages/Planned";
import { CopilotPage } from "./modules/conversation/CopilotPage";
import { FoodPage } from "./modules/nutrition/FoodPage";
import { FreeCarePage } from "./modules/opportunities/FreeCarePage";
import { RemindersPage } from "./modules/reminders/RemindersPage";
import { MedScanPage } from "./modules/medscan/MedScanPage";
import { ConnectionsPage } from "./modules/connections/ConnectionsPage";

// HashRouter: deep links work on GitHub Pages static hosting without a 404 fallback.
export function App() {
  return (
    <AppStateProvider>
      <HashRouter>
        <AppRoutes />
      </HashRouter>
    </AppStateProvider>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Showcase />} />
      <Route path="/app" element={<AppShell />}>
        <Route index element={<Home />} />
        <Route path="copilot" element={<CopilotPage />} />
        <Route path="food" element={<FoodPage />} />
        <Route path="joy" element={<Joy />} />
        <Route path="free-care" element={<FreeCarePage />} />
        <Route path="reminders" element={<RemindersPage />} />
        <Route path="medscan" element={<MedScanPage />} />
        <Route path="connections" element={<ConnectionsPage />} />
        <Route path="settings" element={<Settings />} />
        {["journey", "body", "sisterhood", "care", "guardian"].map((p) => <Route key={p} path={p} element={<Planned path={`/app/${p}`} />} />)}
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
