import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, BrandDashboard as BrandDashboardData, downloadAuthorized } from "../lib/api";
import { KpiCard } from "../components/KpiCard";

const fmtUsd = (n: number) => `$${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
const fmtPct = (n: number) => `${(n * 100).toFixed(1)}%`;

export function BrandDashboardPage() {
  const [data, setData] = useState<BrandDashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.brandDashboard().then(setData).catch((e) => setError(String(e)));
  }, []);

  if (error) return <div className="p-6 text-error">{error}</div>;
  if (!data) return <div className="p-6 label-caps">Loading brand dashboard…</div>;

  return (
    <div className="p-6 max-w-[1440px] mx-auto">
      <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
        <h1 className="text-3xl uppercase">Brand Dashboard</h1>
        <div className="flex gap-3">
          <button
            className="border border-fire text-fire label-caps px-4 py-2 hover:bg-fire/10"
            onClick={() => downloadAuthorized(api.exportAnalysisDeckUrl(), "margin-iq-analysis-deck.pdf")}
          >
            Analysis Deck (PDF)
          </button>
          <button
            className="border border-fire text-fire label-caps px-4 py-2 hover:bg-fire/10"
            onClick={() => downloadAuthorized(api.exportRecommendationsDeckUrl(), "margin-iq-recommendations-deck.pdf")}
          >
            Recs Deck (PDF)
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <KpiCard label="Combined F&B Revenue" value={fmtUsd(data.combined_revenue)} />
        <KpiCard label="Blended Prime Cost %" value={fmtPct(data.blended_prime_cost_pct)} />
        <KpiCard label="Projected BPS Lift" value={`${data.projected_bps_lift.toFixed(0)} BPS`} />
        <KpiCard label="Approved Cash Flow Impact" value={fmtUsd(data.approved_cash_flow_impact)} highlight />
      </div>

      <h2 className="text-xl mb-4 uppercase text-fire">Locations</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {data.locations.map((loc: any) => (
          <Link
            key={loc.location_id}
            to={`/locations/${loc.location_id}`}
            className="border border-outline bg-surface p-5 hover:border-fire transition-colors block"
          >
            <p className="font-display text-xl mb-2">{loc.name}</p>
            {loc.status === "ok" ? (
              <>
                <p className="data-num text-lg text-on-surface">{fmtUsd(loc.revenue)}</p>
                <p className="label-caps mt-2">
                  Prime Cost {fmtPct(loc.prime_cost_pct)} · CM$ {fmtUsd(loc.cm_dollars)}
                </p>
                <p className="label-caps text-on-surface-variant mt-1">{loc.item_count} items analyzed</p>
              </>
            ) : (
              <p className="label-caps text-puzzle">{loc.status.replace("_", " ")}</p>
            )}
          </Link>
        ))}
      </div>

      <h2 className="text-xl mt-10 mb-4 uppercase text-fire">Running Pro Forma</h2>
      <div className="border border-outline bg-surface p-6">
        <div className="flex items-baseline gap-3 mb-4">
          <span className="label-caps">Cumulative Cash-Flow Lift</span>
          <span className="data-num text-3xl text-fire">{fmtUsd(data.pro_forma.brand_period_cash_impact)}</span>
        </div>
        <p className="label-caps">
          {data.pro_forma.queue_progress.approved} approved · {data.pro_forma.queue_progress.pending} pending ·{" "}
          {data.pro_forma.queue_progress.denied} denied
        </p>
      </div>
    </div>
  );
}
