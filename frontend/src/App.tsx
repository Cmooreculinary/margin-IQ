import { Route, Routes } from "react-router-dom";
import { TopNav } from "./components/TopNav";
import { BrandDashboardPage } from "./pages/BrandDashboard";
import { LocationDashboardPage } from "./pages/LocationDashboard";
import { ItemAnalysisTablePage } from "./pages/ItemAnalysisTable";
import { ApprovalQueuePage } from "./pages/ApprovalQueue";
import { ValidationPage } from "./pages/Validation";
import { EngagementPlanPage } from "./pages/EngagementPlan";
import { DocumentUploadPage } from "./pages/DocumentUpload";
import { DriveImportPage } from "./pages/DriveImport";
import { SupplyAgentPage } from "./pages/SupplyAgent";

export function App() {
  return (
    <div className="min-h-screen">
      <TopNav />
      <main className="pt-16">
        <Routes>
          <Route path="/" element={<BrandDashboardPage />} />
          <Route path="/locations/:locationId" element={<LocationDashboardPage />} />
          <Route path="/items" element={<ItemAnalysisTablePage />} />
          <Route path="/approvals" element={<ApprovalQueuePage />} />
          <Route path="/validation" element={<ValidationPage />} />
          <Route path="/engagement" element={<EngagementPlanPage />} />
          <Route path="/documents" element={<DocumentUploadPage />} />
          <Route path="/drive-import" element={<DriveImportPage />} />
          <Route path="/supply-agent" element={<SupplyAgentPage />} />
        </Routes>
      </main>
    </div>
  );
}
