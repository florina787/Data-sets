import { Route, Routes } from "react-router-dom";
import { Layout } from "@/components/common/Layout";
import { EvidenceProvider } from "@/components/evidence/EvidenceContext";
import AskIntelligence from "@/pages/AskIntelligence";
import Leadership from "@/pages/Leadership";
import Sentiment from "@/pages/Sentiment";
import Coaching from "@/pages/Coaching";
import Explorer from "@/pages/Explorer";
import Harness from "@/pages/Harness";
import Prompts from "@/pages/Prompts";
import Metrics from "@/pages/Metrics";
import Governance from "@/pages/Governance";
import { EmptyState } from "@/components/common/ui";

export default function App() {
  return (
    <EvidenceProvider>
      <Layout>
        <Routes>
          <Route path="/" element={<AskIntelligence />} />
          <Route path="/leadership" element={<Leadership />} />
          <Route path="/sentiment" element={<Sentiment />} />
          <Route path="/coaching" element={<Coaching />} />
          <Route path="/explorer" element={<Explorer />} />
          <Route path="/explorer/:conversationId" element={<Explorer />} />
          <Route path="/harness" element={<Harness />} />
          <Route path="/harness/:requestId" element={<Harness />} />
          <Route path="/prompts" element={<Prompts />} />
          <Route path="/metrics" element={<Metrics />} />
          <Route path="/governance" element={<Governance />} />
          <Route path="*" element={<EmptyState title="Page not found" description="Use the navigation to choose a workspace." />} />
        </Routes>
      </Layout>
    </EvidenceProvider>
  );
}
