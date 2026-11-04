import { Navigate, Route, Routes } from "react-router-dom";
import { AppLayout } from "./components/Layout";
import { useAuth } from "./lib/auth";
import Assistant from "./pages/Assistant";
import { Admin, Billing, Governance, McpRegistry, MissionControl, SettingsPage } from "./pages/control";
import { JobDiscovery, Matching, Radar } from "./pages/jobs";
import { Ats, Coding, CoverLetters, InterviewPage, Learning, ResumeStudio } from "./pages/prepare";
import { BillingResult, Landing, Login, Pricing, Register } from "./pages/public";
import { Analytics, Applications, CompanyResearch, Portfolio, Recruiters, Salary } from "./pages/pursue";

function Protected({ children }: { children: JSX.Element }) {
  const { me, loading } = useAuth();
  if (loading) return <div className="grid min-h-dvh place-items-center text-sm text-slate-400">Loading…</div>;
  return me ? children : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/pricing" element={<Pricing />} />
      <Route path="/billing/success" element={<Protected><BillingResult ok /></Protected>} />
      <Route path="/billing/cancel" element={<BillingResult ok={false} />} />
      <Route path="/app" element={<Protected><AppLayout /></Protected>}>
        <Route index element={<Assistant />} />
        <Route path="jobs" element={<JobDiscovery />} />
        <Route path="jobs/indeed" element={<JobDiscovery key="indeed" origin="indeed" />} />
        <Route path="jobs/linkedin" element={<JobDiscovery key="linkedin" origin="linkedin" />} />
        <Route path="radar" element={<Radar />} />
        <Route path="matching" element={<Matching />} />
        <Route path="resume" element={<ResumeStudio />} />
        <Route path="ats" element={<Ats />} />
        <Route path="cover" element={<CoverLetters />} />
        <Route path="interview" element={<InterviewPage />} />
        <Route path="coding" element={<Coding />} />
        <Route path="learning" element={<Learning />} />
        <Route path="company" element={<CompanyResearch />} />
        <Route path="recruiters" element={<Recruiters />} />
        <Route path="applications" element={<Applications />} />
        <Route path="portfolio" element={<Portfolio />} />
        <Route path="salary" element={<Salary />} />
        <Route path="analytics" element={<Analytics />} />
        <Route path="mission" element={<MissionControl />} />
        <Route path="mcp" element={<McpRegistry />} />
        <Route path="governance" element={<Governance />} />
        <Route path="billing" element={<Billing />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="admin" element={<Admin />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
