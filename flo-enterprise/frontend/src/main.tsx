import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { Spinner } from "@/components/ui";
import { AppProvider, useApp } from "@/lib/app";
import Login from "@/pages/Login";
import "./index.css";

const Executive = lazy(() => import("@/pages/Executive"));
const Investment = lazy(() => import("@/pages/Investment"));
const Scenarios = lazy(() => import("@/pages/Scenarios"));
const Wealth = lazy(() => import("@/pages/Wealth"));
const Client360 = lazy(() => import("@/pages/Client360"));
const Products = lazy(() => import("@/pages/Products"));
const Compliance = lazy(() => import("@/pages/Compliance"));
const Approvals = lazy(() => import("@/pages/Approvals"));
const Decisions = lazy(() => import("@/pages/Decisions"));
const Knowledge = lazy(() => import("@/pages/Knowledge"));
const AIOps = lazy(() => import("@/pages/AIOps"));
const Governance = lazy(() => import("@/pages/Governance"));
const Privacy = lazy(() => import("@/pages/Privacy"));
const DataProducts = lazy(() => import("@/pages/DataProducts"));

const qc = new QueryClient({ defaultOptions: { queries: { staleTime: 60_000, retry: (n, e: any) => n < 1 && ![401, 403, 404].includes(e?.status) } } });

function Shell() {
  const { me, loading } = useApp();
  if (loading) return <Spinner label="Starting FLO" />;
  if (!me) return <Login />;
  const home = `/${me.navigation[0]?.id ?? "data"}`;
  return (
    <Layout>
      <Suspense fallback={<Spinner />}>
        <Routes>
          <Route path="/" element={<Navigate to={home} replace />} />
          <Route path="/executive" element={<Executive />} />
          <Route path="/investment" element={<Investment />} />
          <Route path="/scenarios" element={<Scenarios />} />
          <Route path="/wealth" element={<Wealth />} />
          <Route path="/wealth/clients/:id" element={<Client360 />} />
          <Route path="/products" element={<Products />} />
          <Route path="/compliance" element={<Compliance />} />
          <Route path="/approvals" element={<Approvals />} />
          <Route path="/decisions" element={<Decisions />} />
          <Route path="/knowledge" element={<Knowledge />} />
          <Route path="/aiops" element={<AIOps />} />
          <Route path="/governance" element={<Governance />} />
          <Route path="/privacy" element={<Privacy />} />
          <Route path="/data" element={<DataProducts />} />
          <Route path="*" element={<Navigate to={home} replace />} />
        </Routes>
      </Suspense>
    </Layout>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <QueryClientProvider client={qc}>
    <AppProvider>
      <BrowserRouter><Shell /></BrowserRouter>
    </AppProvider>
  </QueryClientProvider>,
);
