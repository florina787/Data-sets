import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppStateProvider } from "./lib/app-state";
import { AppShell } from "./components/AppShell";
import { HomePage } from "./site/pages/HomePage";
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
const BodyPage = lazy(() => import("./modules/body/BodyPage").then((m) => ({ default: m.BodyPage })));
const GuardianPage = lazy(() => import("./modules/guardian/GuardianPage").then((m) => ({ default: m.GuardianPage })));
const SisterhoodPage = lazy(() => import("./modules/sisterhood/SisterhoodPage").then((m) => ({ default: m.SisterhoodPage })));
const HelpPage = lazy(() => import("./modules/onboarding/HelpPage").then((m) => ({ default: m.HelpPage })));
const FeaturesPage = lazy(() => import("./site/pages/FeaturesPage").then((m) => ({ default: m.FeaturesPage })));
const DemoPage = lazy(() => import("./site/pages/DemoPage").then((m) => ({ default: m.DemoPage })));
const ClubPage = lazy(() => import("./site/pages/ClubPage").then((m) => ({ default: m.ClubPage })));
const HowItWorksPage = lazy(() => import("./site/pages/HowItWorksPage").then((m) => ({ default: m.HowItWorksPage })));
const GalleryPage = lazy(() => import("./site/pages/GalleryPage").then((m) => ({ default: m.GalleryPage })));
const PricingPage = lazy(() => import("./site/pages/PricingPage").then((m) => ({ default: m.PricingPage })));
const TrustPage = lazy(() => import("./site/pages/TrustPage").then((m) => ({ default: m.TrustPage })));
const Joy = lazy(() => import("./pages/Joy").then((m) => ({ default: m.Joy })));
const Settings = lazy(() => import("./pages/Settings").then((m) => ({ default: m.Settings })));

function Loading() {
  return <div role="status" aria-label="Loading" className="grid min-h-[40vh] place-items-center"><span className="h-10 w-10 animate-spin rounded-full border-2 border-line border-t-accent" /></div>;
}

// Clean URLs under the GitHub Pages base path. Direct loads/refreshes work because the build writes an
// index.html per public page and a 404.html fallback for app routes (scripts/postbuild.mjs).
export const BASENAME = import.meta.env.BASE_URL.replace(/\/$/, "");
export function App() {
  return (
    <AppStateProvider>
      <BrowserRouter basename={BASENAME}>
        <AppRoutes />
      </BrowserRouter>
    </AppStateProvider>
  );
}

export function AppRoutes() {
  return (
    <Suspense fallback={<Loading />}>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/features" element={<FeaturesPage />} />
        <Route path="/demo" element={<DemoPage />} />
        <Route path="/club" element={<ClubPage />} />
        <Route path="/how-it-works" element={<HowItWorksPage />} />
        <Route path="/gallery" element={<GalleryPage />} />
        <Route path="/pricing" element={<PricingPage />} />
        <Route path="/trust" element={<TrustPage />} />
        <Route path="/app" element={<AppShell />}>
          <Route index element={<Home />} />
          <Route path="copilot" element={<CopilotPage />} />
          <Route path="food" element={<FoodPage />} />
          <Route path="joy" element={<Joy />} />
          <Route path="journey" element={<JourneyPage />} />
          <Route path="body" element={<BodyPage />} />
          <Route path="guardian" element={<GuardianPage />} />
          <Route path="sisterhood" element={<SisterhoodPage />} />
          <Route path="help" element={<HelpPage />} />
          <Route path="free-care" element={<FreeCarePage />} />
          <Route path="reminders" element={<RemindersPage />} />
          <Route path="medscan" element={<MedScanPage />} />
          <Route path="connections" element={<ConnectionsPage />} />
          <Route path="settings" element={<Settings />} />
          {["care"].map((p) => <Route key={p} path={p} element={<Planned path={`/app/${p}`} />} />)}
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
