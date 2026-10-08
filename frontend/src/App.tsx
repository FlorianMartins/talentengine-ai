import { BrowserRouter, Route, Routes } from "react-router-dom";
import { PrefsProvider, SystemProvider, ToastProvider } from "./lib/prefs";
import { Shell } from "./components/Shell";
import { OverviewPage } from "./pages/Overview";
import { StudioPage } from "./pages/Studio";
import { PipelinePage } from "./pages/Pipeline";
import { ApplyPage } from "./pages/Apply";
import { ReportPage } from "./pages/Report";
import { AuditPage } from "./pages/Audit";
import { SettingsPage } from "./pages/Settings";
import { NotFoundPage } from "./pages/NotFound";

export function App() {
  return (
    <PrefsProvider>
      <ToastProvider>
        <SystemProvider>
          <BrowserRouter>
            <Routes>
              <Route element={<Shell />}>
                <Route index element={<OverviewPage />} />
                <Route path="jobs/new" element={<StudioPage />} />
                <Route path="jobs/:id/edit" element={<StudioPage />} />
                <Route path="jobs/:id/apply" element={<ApplyPage />} />
                <Route path="jobs/:id" element={<PipelinePage />} />
                <Route path="candidates/:ref" element={<ReportPage />} />
                <Route path="audit" element={<AuditPage />} />
                <Route path="settings" element={<SettingsPage />} />
                <Route path="*" element={<NotFoundPage />} />
              </Route>
            </Routes>
          </BrowserRouter>
        </SystemProvider>
      </ToastProvider>
    </PrefsProvider>
  );
}
