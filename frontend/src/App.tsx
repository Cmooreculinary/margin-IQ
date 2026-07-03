import { Route, Routes } from "react-router-dom";
import { TopNav } from "./components/TopNav";
import { BrandDashboardPage } from "./pages/BrandDashboard";
import { LocationDashboardPage } from "./pages/LocationDashboard";
import { ItemAnalysisTablePage } from "./pages/ItemAnalysisTable";
import { ApprovalQueuePage } from "./pages/ApprovalQueue";

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
        </Routes>
      </main>
    </div>
  );
}
