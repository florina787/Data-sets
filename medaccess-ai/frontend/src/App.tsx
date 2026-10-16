import type { ReactElement } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { useApp } from "./hooks/AppContext";
import { AppLayout } from "./layouts/AppLayout";
import {
  AdminPage, ApprovalsPage, ArchitecturePage, CommandCenterPage, DevelopmentPage, MetricsPage, MonitoringPage,
  ObservabilityPage, QAPage, ReleasesPage, RequirementsPage, SecurityPage,
} from "./pages/engineering";
import { LoginPage } from "./pages/LoginPage";
import {
  AgentActivityPage, AgentGraphPage, ChristinaPage, ComparePage, DashboardPage, FacilitiesPage, HistoryPage, MapPage,
  NotificationsPage, PreferencesPage, RequisitionPage, SearchPage, SettingsPage, TrackerPage,
} from "./pages/patient";
import type { Role } from "./services/api";

const ENG: Role[] = ["engineer", "release_approver", "admin"];

function Guard({ roles, children }: { roles: Role[]; children: ReactElement }) {
  const { user } = useApp();
  if (!user || !roles.includes(user.role)) {
    return <div className="card p-6"><h1 className="h1">Not available for your role</h1><p className="muted mt-2">This page is restricted. Patient-facing accounts cannot access engineering or administrative pages.</p></div>;
  }
  return children;
}

export default function App() {
  const { user } = useApp();
  if (!user) return <LoginPage />;
  return (
    <AppLayout>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/search/:service" element={<SearchPage />} />
        <Route path="/facilities" element={<FacilitiesPage />} />
        <Route path="/map" element={<MapPage />} />
        <Route path="/compare" element={<ComparePage />} />
        <Route path="/tracker" element={<TrackerPage />} />
        <Route path="/notifications" element={<NotificationsPage />} />
        <Route path="/saved" element={<HistoryPage saved />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/requisition" element={<RequisitionPage />} />
        <Route path="/preferences" element={<PreferencesPage />} />
        <Route path="/christina" element={<ChristinaPage />} />
        <Route path="/agent-activity" element={<AgentActivityPage />} />
        <Route path="/agent-graph" element={<AgentGraphPage />} />
        <Route path="/sdlc" element={<Guard roles={ENG}><CommandCenterPage /></Guard>} />
        <Route path="/requirements" element={<Guard roles={ENG}><RequirementsPage /></Guard>} />
        <Route path="/architecture" element={<Guard roles={ENG}><ArchitecturePage /></Guard>} />
        <Route path="/development" element={<Guard roles={ENG}><DevelopmentPage /></Guard>} />
        <Route path="/qa" element={<Guard roles={ENG}><QAPage /></Guard>} />
        <Route path="/security" element={<Guard roles={ENG}><SecurityPage /></Guard>} />
        <Route path="/approvals" element={<ApprovalsPage />} />
        <Route path="/releases" element={<Guard roles={ENG}><ReleasesPage /></Guard>} />
        <Route path="/monitoring" element={<Guard roles={ENG}><MonitoringPage /></Guard>} />
        <Route path="/observability" element={<Guard roles={ENG}><ObservabilityPage /></Guard>} />
        <Route path="/metrics" element={<Guard roles={ENG}><MetricsPage /></Guard>} />
        <Route path="/admin" element={<Guard roles={["admin"]}><AdminPage /></Guard>} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AppLayout>
  );
}
