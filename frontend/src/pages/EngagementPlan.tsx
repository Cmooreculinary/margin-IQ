import { useEffect, useMemo, useState } from "react";
import { api, EngagementPlan } from "../lib/api";

const fmtUsd = (n: number) => `$${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;

function Checklist({ items }: { items: string[] }) {
  return (
    <ul className="space-y-2 text-sm text-on-surface-variant">
      {items.map((item) => (
        <li key={item} className="flex gap-2">
          <span className="mt-1 h-1.5 w-1.5 shrink-0 bg-fire" />
          <span>{item}</span>
        </li>
      ))}
    </ul>
  );
}

export function EngagementPlanPage() {
  const [data, setData] = useState<EngagementPlan | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.engagementPlan().then(setData).catch((e) => setError(String(e)));
  }, []);

  const deliverablesByCategory = useMemo(() => {
    const buckets: Record<string, EngagementPlan["plan"]["deliverables"]> = {};
    for (const deliverable of data?.plan.deliverables ?? []) {
      buckets[deliverable.category] = buckets[deliverable.category] ?? [];
      buckets[deliverable.category].push(deliverable);
    }
    return buckets;
  }, [data]);

  if (error) return <div className="p-6 text-error">{error}</div>;
  if (!data) return <div className="p-6 label-caps">Loading engagement plan...</div>;

  const { plan } = data;

  return (
    <div className="p-6 max-w-[1440px] mx-auto">
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4 mb-8">
        <div>
          <p className="label-caps text-fire mb-2">Consulting Proposal | {plan.proposal_month}</p>
          <h1 className="text-4xl uppercase">{plan.brand_name}</h1>
          <p className="text-on-surface-variant mt-2">
            Menu Profitability Intelligence | {plan.scope.locations.length} US Locations | Start {plan.engagement_start}
          </p>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 min-w-[320px]">
          <div className="border border-outline bg-surface p-4">
            <p className="label-caps mb-1">US Locations</p>
            <p className="data-num text-2xl text-fire">{plan.scope.locations.length}</p>
          </div>
          <div className="border border-outline bg-surface p-4">
            <p className="label-caps mb-1">F&B Revenue</p>
            <p className="data-num text-2xl">{fmtUsd(plan.scope.annual_fnb_revenue_estimate)}</p>
          </div>
          <div className="border border-outline bg-surface p-4">
            <p className="label-caps mb-1">Delivery</p>
            <p className="data-num text-2xl">2-3 wks</p>
          </div>
          <div className="border border-fire bg-surface p-4 shadow-glow">
            <p className="label-caps text-fire mb-1">ROI Payback</p>
            <p className="data-num text-2xl text-fire">&lt;{plan.scope.target_roi_payback_days} days</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[1.2fr_0.8fr] gap-6 mb-8">
        <section className="border border-outline bg-surface p-5">
          <h2 className="text-2xl uppercase text-fire mb-4">Engagement Timeline</h2>
          <div className="space-y-4">
            {plan.timeline.map((phase) => (
              <div key={phase.phase} className="border border-outline bg-obsidian p-4">
                <div className="flex flex-wrap items-baseline justify-between gap-3 mb-3">
                  <h3 className="font-display text-xl uppercase">
                    {phase.phase} | {phase.name}
                  </h3>
                  <span className="label-caps text-fire">{phase.timing}</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  <div>
                    <p className="label-caps mb-2">Needs</p>
                    <Checklist items={phase.needs} />
                  </div>
                  <div>
                    <p className="label-caps mb-2">Deliverables</p>
                    <Checklist items={phase.deliverables} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>

        <aside className="space-y-6">
          <section className="border border-outline bg-surface p-5">
            <h2 className="text-xl uppercase text-fire mb-4">Data Requirements</h2>
            <Checklist items={plan.data_requirements} />
          </section>

          <section className="border border-outline bg-surface p-5">
            <h2 className="text-xl uppercase text-fire mb-4">Engagement Terms</h2>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between gap-4">
                <span className="label-caps">Project Fee</span>
                <span className="data-num">{fmtUsd(plan.terms.project_fee)}</span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="label-caps">Invoice 1</span>
                <span className="data-num">{fmtUsd(plan.terms.invoice_1)}</span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="label-caps">Invoice 2</span>
                <span className="data-num">{fmtUsd(plan.terms.invoice_2)}</span>
              </div>
              <p className="text-on-surface-variant pt-3">{plan.terms.payment_structure}</p>
              <p className="text-on-surface-variant">{plan.terms.onsite_review}</p>
            </div>
          </section>

          <section className="border border-outline bg-surface p-5">
            <h2 className="text-xl uppercase text-fire mb-4">Guardrails</h2>
            <Checklist items={plan.scope.guardrails} />
          </section>
        </aside>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className="border border-outline bg-surface p-5">
          <h2 className="text-2xl uppercase text-fire mb-4">Deliverables</h2>
          <div className="space-y-5">
            {Object.entries(deliverablesByCategory).map(([category, deliverables]) => (
              <div key={category}>
                <p className="label-caps mb-2">{category}</p>
                <div className="border border-outline">
                  {deliverables.map((deliverable) => (
                    <div key={deliverable.name} className="grid grid-cols-[1fr_auto] gap-4 border-b border-outline/50 last:border-b-0 px-3 py-2 text-sm">
                      <span>{deliverable.name}</span>
                      <span className="label-caps text-fire">{deliverable.status}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="border border-outline bg-surface p-5">
          <h2 className="text-2xl uppercase text-fire mb-4">Franchise System Test</h2>
          <Checklist items={plan.franchise_angle} />
          <div className="mt-6 border border-outline bg-obsidian p-4">
            <p className="label-caps text-fire mb-2">Full-Scale Demo Coverage</p>
            <p className="text-sm text-on-surface-variant">
              This tenant includes reconciled baseline data, post-implementation validation actuals,
              excluded game-fee revenue, labor allocation, competitor benchmarks, item recommendations,
              approval workflow, pro formas, XLSX exports, and PDF deliverables across Chicago, Tempe,
              and Tucson.
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}
