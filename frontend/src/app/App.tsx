import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { ProjectList } from "../components/ProjectList";
import { IngestFlowView } from "../routes/IngestFlowView";
import { PreprocessView } from "../routes/PreprocessView";

const queryClient = new QueryClient();

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<ProjectList />} />
          <Route path="/projects/:slug/ingest" element={<IngestFlowView />} />
          <Route path="/projects/:slug/preprocess" element={<PreprocessView />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
