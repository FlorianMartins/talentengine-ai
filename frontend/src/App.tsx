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
import { AccountsPage } from "./pages/Accounts";
import { CompliancePage } from "./pages/Compliance";
import { IntegrationsPage } from "./pages/Integrations";
import { lazy, Suspense, type ReactNode } from "react";

// Public pages are split out: a candidate opening the shared link only downloads what they need.
const TryPage = lazy(() => import("./pages/Try").then((m) => ({ default: m.TryPage })));
const ExplanationPage = lazy(() => import("./pages/Explanation").then((m) => ({ default: m.ExplanationPage })));
const TestPlayerPage = lazy(() => import("./pages/TestPlayer").then((m) => ({ default: m.TestPlayerPage })));
const PilotPlayerPage = lazy(() => import("./pages/PilotPlayer").then((m) => ({ default: m.PilotPlayerPage })));
const RecruitersPage = lazy(() => import("./pages/Recruiters").then((m) => ({ default: m.RecruitersPage })));
const Lazy = ({ children }: { children: ReactNode }) => <Suspense fallback={<div className="public" />}>{children}</Suspense>;

export function App() {
  return (
    <PrefsProvider>
      <ToastProvider>
        <BrowserRouter basename={import.meta.env.BASE_URL.replace(/\/$/, "")}>
            <Routes>
              {/* public pages: no app shell, no API key */}
              <Route path="essai" element={<Lazy><TryPage lang="fr" /></Lazy>} />
              <Route path="try" element={<Lazy><TryPage lang="en" /></Lazy>} />
              <Route path="test/:token" element={<Lazy><TestPlayerPage /></Lazy>} />
              <Route path="en/test/:token" element={<Lazy><TestPlayerPage /></Lazy>} />
              <Route path="pilote/:token" element={<Lazy><PilotPlayerPage /></Lazy>} />
              <Route path="en/pilote/:token" element={<Lazy><PilotPlayerPage /></Lazy>} />
              <Route path="explication/:token" element={<Lazy><ExplanationPage lang="fr" /></Lazy>} />
              <Route path="explanation/:token" element={<Lazy><ExplanationPage lang="en" /></Lazy>} />
              <Route path="recruteurs" element={<Lazy><RecruitersPage lang="fr" /></Lazy>} />
              <Route path="recruiters" element={<Lazy><RecruitersPage lang="en" /></Lazy>} />
              {/* the system status (runtime, ledger) needs the API key: only the recruiter app loads it */}
              <Route element={<SystemProvider><Shell /></SystemProvider>}>
                <Route index element={<OverviewPage />} />
                <Route path="jobs/new" element={<StudioPage />} />
                <Route path="jobs/:id/edit" element={<StudioPage />} />
                <Route path="jobs/:id/apply" element={<ApplyPage />} />
                <Route path="jobs/:id" element={<PipelinePage />} />
                <Route path="candidates/:ref" element={<ReportPage />} />
                <Route path="audit" element={<AuditPage />} />
                <Route path="settings" element={<SettingsPage />} />
                <Route path="settings/accounts" element={<AccountsPage />} />
                <Route path="settings/integrations" element={<IntegrationsPage />} />
                <Route path="compliance" element={<CompliancePage />} />
                <Route path="*" element={<NotFoundPage />} />
              </Route>
            </Routes>
        </BrowserRouter>
      </ToastProvider>
    </PrefsProvider>
  );
}
