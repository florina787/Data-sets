import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { Layout, useLogin } from "@/components/Layout";
import { ErrorBox, Loading } from "@/components/ui";
import { rememberedUser, useSession } from "@/lib/store";
import { MissionControl } from "@/features/copilot/MissionControl";
import { FleetPage } from "@/features/fleet/FleetPage";
import { AogPage } from "@/features/aog/AogPage";
import { MaintenancePage } from "@/features/maintenance/MaintenancePage";
import { PartsPage } from "@/features/parts/PartsPage";
import { QualityPage } from "@/features/quality/QualityPage";
import { LegacyPage } from "@/features/legacy/LegacyPage";
import { BridgePage } from "@/features/bridge/BridgePage";
import { AgentsPage } from "@/features/agents/AgentsPage";
import { TrustPage } from "@/features/governance/TrustPage";
import { CompliancePage } from "@/features/governance/CompliancePage";
import { SimulatorPage } from "@/features/simulator/SimulatorPage";
import { ExecutivePage } from "@/features/executive/ExecutivePage";
import { ReportsPage } from "@/features/reports/ReportsPage";
import { SettingsPage } from "@/features/settings/SettingsPage";
import { CommandCenter } from "@/features/command/CommandCenter";
import { PredictiveMaintenance } from "@/features/predictive/PredictiveMaintenance";
import { Observability } from "@/features/observability/Observability";

// 3.0 pages are code-split so the map and model views do not slow the first load of the chat.
const GlobalIntelligence = lazy(() => import("@/features/global/GlobalIntelligence").then((m) => ({ default: m.GlobalIntelligence })));
const ComponentForecasting = lazy(() => import("@/features/v3/ComponentForecasting").then((m) => ({ default: m.ComponentForecasting })));
const DigitalTwin = lazy(() => import("@/features/v3/DigitalTwin").then((m) => ({ default: m.DigitalTwin })));
const SupplyChain = lazy(() => import("@/features/v3/SupplyChain").then((m) => ({ default: m.SupplyChain })));
const Resilience = lazy(() => import("@/features/v3/Resilience").then((m) => ({ default: m.Resilience })));
const ControlTower = lazy(() => import("@/features/v3/ControlTower").then((m) => ({ default: m.ControlTower })));
const AirspaceLab = lazy(() => import("@/features/v3/AirspaceLab").then((m) => ({ default: m.AirspaceLab })));
const ChangeImpact = lazy(() => import("@/features/v3/ChangeImpact").then((m) => ({ default: m.ChangeImpact })));
const lazyPage = (el: React.ReactNode) => <Suspense fallback={<Loading label="Loading" />}>{el}</Suspense>;

export function App() {
  const token = useSession((s) => s.token);
  const expired = useSession((s) => s.expired);
  const login = useLogin();
  const [error, setError] = useState<unknown>(null);
  const inFlight = useRef(false);
  useEffect(() => {
    if ((!token || expired) && !inFlight.current) {
      inFlight.current = true;
      login(rememberedUser()).catch(setError).finally(() => (inFlight.current = false));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [expired]);
  if (error) return <div className="p-8"><ErrorBox error={error} onRetry={() => login("planner.marco").then(() => setError(null)).catch(setError)} /></div>;
  if (!token) return <Loading label="Starting local demo session" />;
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<MissionControl />} />
        <Route path="/fleet" element={<FleetPage />} />
        <Route path="/aog" element={<AogPage />} />
        <Route path="/maintenance" element={<MaintenancePage />} />
        <Route path="/parts" element={<PartsPage />} />
        <Route path="/quality" element={<QualityPage />} />
        <Route path="/legacy" element={<LegacyPage />} />
        <Route path="/bridge" element={<BridgePage />} />
        <Route path="/agents" element={<AgentsPage />} />
        <Route path="/trust" element={<TrustPage />} />
        <Route path="/compliance" element={<CompliancePage />} />
        <Route path="/simulator" element={<SimulatorPage />} />
        <Route path="/executive" element={<ExecutivePage />} />
        <Route path="/reports" element={<ReportsPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/command" element={<CommandCenter />} />
        <Route path="/predictive" element={<PredictiveMaintenance />} />
        <Route path="/observability" element={<Observability />} />
        <Route path="/global" element={lazyPage(<GlobalIntelligence />)} />
        <Route path="/forecasting" element={lazyPage(<ComponentForecasting />)} />
        <Route path="/twin" element={lazyPage(<DigitalTwin />)} />
        <Route path="/supply" element={lazyPage(<SupplyChain />)} />
        <Route path="/resilience" element={lazyPage(<Resilience />)} />
        <Route path="/control-tower" element={lazyPage(<ControlTower />)} />
        <Route path="/airspace" element={lazyPage(<AirspaceLab />)} />
        <Route path="/change-impact" element={lazyPage(<ChangeImpact />)} />
        <Route path="/chat" element={<Navigate to="/" replace />} />
        {/* 2.0 aliases for the section names; every pre-2.0 route above still works */}
        <Route path="/assistant" element={<Navigate to="/" replace />} />
        <Route path="/recovery" element={<Navigate to="/aog" replace />} />
        <Route path="/governance" element={<Navigate to="/trust" replace />} />
        <Route path="/integrations" element={<Navigate to="/bridge" replace />} />
        <Route path="*" element={<div className="p-8">Page not found.</div>} />
      </Routes>
    </Layout>
  );
}
