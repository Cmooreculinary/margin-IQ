import { Link } from "react-router-dom";
import { ProductCapabilities } from "../lib/api";

export function SuiteHomePage({ capabilities }: { capabilities: ProductCapabilities }) {
  return (
    <div className="p-6 max-w-[1200px] mx-auto">
      <div className="mb-8">
        <p className="label-caps text-fire mb-2">BCA Hospitality Intelligence</p>
        <h1 className="text-4xl uppercase mb-3">Two Products. One Controlled Workspace.</h1>
        <p className="text-on-surface-variant max-w-3xl">
          Margin IQ and Supply Agent remain independently licensed and independently callable.
          Suite mode gives {capabilities.tenant_name} one tenant identity, one navigation layer,
          and a clean integration contract without coupling either product&apos;s core workflow.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <section className="border border-outline bg-surface p-6">
          <p className="label-caps text-fire mb-2">Standalone Product</p>
          <h2 className="text-3xl uppercase mb-3">Margin IQ</h2>
          <p className="text-on-surface-variant mb-6">
            Prime-cost menu profitability, item engineering, approval-controlled recommendations,
            pro formas, and post-implementation validation.
          </p>
          <Link className="label-caps inline-block border border-fire text-fire px-4 py-2" to="/margin">
            Open Margin IQ
          </Link>
        </section>

        <section className="border border-outline bg-surface p-6">
          <p className="label-caps text-fire mb-2">Standalone Product</p>
          <h2 className="text-3xl uppercase mb-3">Supply Agent</h2>
          <p className="text-on-surface-variant mb-6">
            Supplier price comparisons, confidence-scored matching, standalone catalogs,
            and auditable savings analysis.
          </p>
          <Link className="label-caps inline-block border border-fire text-fire px-4 py-2" to="/supply-agent">
            Open Supply Agent
          </Link>
        </section>
      </div>

      <section className="border border-outline bg-obsidian p-6">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <h2 className="text-2xl uppercase">Suite Integration Boundary</h2>
          <span className="label-caps text-star">Contract Ready</span>
        </div>
        <p className="text-on-surface-variant mb-4">{capabilities.integration.description}</p>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
          <div className="border border-outline/60 p-4">
            <p className="label-caps text-fire mb-1">Shared</p>
            <p>Tenant identity, authentication, product discovery, and deployment.</p>
          </div>
          <div className="border border-outline/60 p-4">
            <p className="label-caps text-fire mb-1">Separate</p>
            <p>Routes, collections, navigation access, commercial entitlement, and workflows.</p>
          </div>
          <div className="border border-outline/60 p-4">
            <p className="label-caps text-fire mb-1">Controlled Handoff</p>
            <p>Supplier-cost data enters Margin IQ only through a future approved mapping contract.</p>
          </div>
        </div>
      </section>
    </div>
  );
}
