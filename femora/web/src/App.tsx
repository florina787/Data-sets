import { lazy, Suspense } from "react";
import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppStateProvider } from "./lib/app-state";
import { AppShell } from "./components/AppShell";
import { Showcase } from "./pages/Showcase";
import { Home } from "./pages/Home";
import { Planned } from "./pages/Planned";

// Route-level code splitting: heavy modules (charts, forms) load only when visited.
const CopilotPage = lazy(() => import("./modules/conversation/CopilotPage").then((m) => ({ default: m.CopilotPage })));
const FoodPage = lazy(() => import("./modules/nutrition/FoodPage").then((m) => ({ default: m.FoodPage })));
const FreeCarePage = lazy(() => import("./modules/opportunities/FreeCarePage").then((m) => ({ default: m.FreeCarePage })));
const RemindersPage = lazy(() => import("./modules/reminders/RemindersPage").then((m) => ({ default: m.RemindersPage })));
const MedScanPage = lazy(() => import("./modules/medscan/MedScanPage").then((m) => ({ default: m.MedScanPage })));
const ConnectionsPage = lazy(() => import("./modules/connections/ConnectionsPage").then((m) => ({ default: m.ConnectionsPage })));
const JourneyPage = lazy(() => import("./modules/journey/JourneyPage").then((m) => ({ default: m.JourneyPage })));
const Joy = lazy(() => import("./pages/Joy").then((m) => ({ default: m.Joy })));
const Settings = lazy(() => import("./pages/Settings").then((m) => ({ default: m.Settings })));

function Loading() {
  return <div role="status" aria-label="Loading" className="grid min-h-[40vh] place-items-center"><span className="h-10 w-10 animate-spin rounded-full border-2 border-line border-t-accent" /></div>;
}

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
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/" element={<Showcase />} />
        <Route path="/app" element={<AppShell />}>
          <Route index element={<Home />} />
          <Route path="copilot" element={<CopilotPage />} />
          <Route path="food" element={<FoodPage />} />
          <Route path="joy" element={<Joy />} />
          <Route path="journey" element={<JourneyPage />} />
          <Route path="free-care" element={<FreeCarePage />} />
          <Route path="reminders" element={<RemindersPage />} />
          <Route path="medscan" element={<MedScanPage />} />
          <Route path="connections" element={<ConnectionsPage />} />
          <Route path="settings" element={<Settings />} />
          {["body", "sisterhood", "care", "guardian"].map((p) => <Route key={p} path={p} element={<Planned path={`/app/${p}`} />} />)}
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
