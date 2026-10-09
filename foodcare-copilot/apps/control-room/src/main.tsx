import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { AppProvider } from "./context";
import "./index.css";
import Board from "./screens/Board";
import Brief from "./screens/Brief";
import Compliance from "./screens/Compliance";
import CopilotPage from "./screens/Copilot";
import Engineering from "./screens/Engineering";
import Evidence from "./screens/Evidence";
import Executive from "./screens/Executive";
import Incidents from "./screens/Incidents";
import Inventory from "./screens/Inventory";
import Overview from "./screens/Overview";
import Quality from "./screens/Quality";
import Releases from "./screens/Releases";
import Requirements from "./screens/Requirements";
import Sales from "./screens/Sales";
import Templates from "./screens/Templates";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <AppProvider>
        <Layout>
          <Routes>
            <Route path="/" element={<Executive />} />
            <Route path="/copilot" element={<CopilotPage />} />
            <Route path="/sales" element={<Sales />} />
            <Route path="/inventory" element={<Inventory />} />
            <Route path="/compliance" element={<Compliance />} />
            <Route path="/delivery" element={<Overview />} />
            <Route path="/brief" element={<Brief />} />
            <Route path="/board" element={<Board />} />
            <Route path="/requirements" element={<Requirements />} />
            <Route path="/engineering" element={<Engineering />} />
            <Route path="/quality" element={<Quality />} />
            <Route path="/releases" element={<Releases />} />
            <Route path="/incidents" element={<Incidents />} />
            <Route path="/templates" element={<Templates />} />
            <Route path="/evidence" element={<Evidence />} />
            <Route path="*" element={<p>Page not found.</p>} />
          </Routes>
        </Layout>
      </AppProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
