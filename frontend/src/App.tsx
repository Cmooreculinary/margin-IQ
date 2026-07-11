import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { TopNav } from "./components/TopNav";
import { api, ProductCapabilities } from "./lib/api";
import { ApprovalQueuePage } from "./pages/ApprovalQueue";
import { BrandDashboardPage } from "./pages/BrandDashboard";
import { DocumentUploadPage } from "./pages/DocumentUpload";
import { EngagementPlanPage } from "./pages/EngagementPlan";
import { ItemAnalysisTablePage } from "./pages/ItemAnalysisTable";
import { LocationDashboardPage } from "./pages/LocationDashboard";
import { SuiteHomePage } from "./pages/SuiteHome";
import { SupplyAgentPage } from "./pages/SupplyAgent";
import { ValidationPage } from "./pages/Validation";

export function App() {
  const [capabilities, setCapabilities] = useState<ProductCapabilities | null>(null);
  const [error, setError] = useState<string>("");

  useEffect(() => {
    api.productCapabilities().then(setCapabilities).catch((err: Error) => setError(err.message));
  }, []);

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center p-6">
        <div className="border border-outline bg-surface p-6 max-w-xl">
          <h1 className="text-3xl uppercase mb-3">Product Access Error</h1>
          <p className="text-on-surface-variant">{error}</p>
        </div>
      </div>
    );
  }

  if (!capabilities) {
    return <div className="min-h-screen flex items-center justify-center label-caps">Loading product access...</div>;
  }

  const marginEnabled = capabilities.enabled_products.includes("margin_iq");
  const supplyEnabled = capabilities.enabled_products.includes("supply_agent");
  const fallbackPath = capabilities.suite_enabled ? "/" : marginEnabled ? "/" : "/supply-agent";

  const home = capabilities.suite_enabled ? (
    <SuiteHomePage capabilities={capabilities} />
  ) : marginEnabled ? (
    <BrandDashboardPage />
  ) : (
    <Navigate to="/supply-agent" replace />
  );

  return (
    <div className="min-h-screen">
      <TopNav capabilities={capabilities} />
      <main className="pt-16">
        <Routes>
          <Route path="/" element={home} />

          {marginEnabled && (
            <>
              <Route
                path="/margin"
                element={capabilities.suite_enabled ? <BrandDashboardPage /> : <Navigate to="/" replace />}
              />
              <Route path="/locations/:locationId" element={<LocationDashboardPage />} />
              <Route path="/items" element={<ItemAnalysisTablePage />} />
              <Route path="/approvals" element={<ApprovalQueuePage />} />
              <Route path="/validation" element={<ValidationPage />} />
              <Route path="/engagement" element={<EngagementPlanPage />} />
              <Route path="/documents" element={<DocumentUploadPage />} />
            </>
          )}

          {supplyEnabled && <Route path="/supply-agent" element={<SupplyAgentPage />} />}

          <Route path="*" element={<Navigate to={fallbackPath} replace />} />
        </Routes>
      </main>
    </div>
  );
}
