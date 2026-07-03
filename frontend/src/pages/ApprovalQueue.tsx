import { useEffect, useState } from "react";
import { api, downloadAuthorized, ProForma, Recommendation } from "../lib/api";

const fmtUsd = (n: number) => `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

export function ApprovalQueuePage() {
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [proForma, setProForma] = useState<ProForma | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = () => {
    api.listRecommendations({ status: "pending" }).then(setRecs).catch((e) => setError(String(e)));
    api.proForma().then(setProForma).catch((e) => setError(String(e)));
  };

  useEffect(refresh, []);

  const decide = async (rec: Recommendation, status: "approved" | "denied") => {
    await api.decideRecommendation(rec._id, status, "demo-operator");
    refresh();
  };

  return (
    <div className="p-6 max-w-[1440px] mx-auto flex flex-col lg:flex-row gap-6">
      <section className="flex-1 space-y-3">
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-3xl uppercase">Recommendations Approval Queue</h1>
          <span className="label-caps">{recs.length} Pending Actions</span>
        </div>
        {error && <div className="text-error">{error}</div>}

        {recs.map((rec) => (
          <div key={rec._id} className="border border-outline bg-surface p-5 hover:border-fire transition-colors">
            <div className="flex justify-between items-start gap-4 flex-wrap">
              <div className="flex-1 min-w-[280px]">
                <div className="flex items-center gap-3 mb-2 flex-wrap">
                  <h3 className="font-display text-xl">{rec.name}</h3>
                  <span className="label-caps text-fire">{rec.location_name}</span>
                  <span className="label-caps border border-outline px-2 py-0.5">{rec.type.toUpperCase()}</span>
                </div>
                <p className="text-sm text-on-surface-variant mb-3">{rec.rationale}</p>
                <div className="flex flex-wrap gap-8">
                  {rec.type === "price" && (
                    <div>
                      <p className="label-caps mb-1">Price Adjust</p>
                      <div className="flex items-baseline gap-2 data-num">
                        <span className="line-through text-on-surface-variant">${rec.current_price.toFixed(2)}</span>
                        <span className="text-fire">→</span>
                        <span className="text-xl text-fire">${rec.recommended_price?.toFixed(2)}</span>
                      </div>
                    </div>
                  )}
                  {rec.projected_bps_lift !== null && (
                    <div>
                      <p className="label-caps mb-1">Projected Lift</p>
                      <p className="data-num text-xl text-star">+{rec.projected_bps_lift} BPS</p>
                    </div>
                  )}
                  {rec.pmix_offset_pct !== null && (
                    <div>
                      <p className="label-caps mb-1">PMIX Effect</p>
                      <p className="data-num">{(rec.pmix_offset_pct * 100).toFixed(1)}% Offset</p>
                    </div>
                  )}
                </div>
              </div>
              <div className="flex flex-col gap-2 w-32">
                <button className="bg-fire text-obsidian label-caps py-2 hover:brightness-110" onClick={() => decide(rec, "approved")}>
                  Approve
                </button>
                <button className="border border-error text-error label-caps py-2 hover:bg-error/10" onClick={() => decide(rec, "denied")}>
                  Deny
                </button>
              </div>
            </div>
          </div>
        ))}
        {recs.length === 0 && !error && <p className="label-caps text-on-surface-variant">Queue is clear -- nothing pending.</p>}
      </section>

      <aside className="lg:w-[320px] shrink-0">
        <div className="border border-outline bg-surface p-6 sticky top-20">
          <h2 className="label-caps text-fire mb-4">Running Pro Forma</h2>
          <p className="label-caps mb-1">Cumulative Cash-Flow Lift</p>
          <div className="data-num text-4xl text-fire mb-6">{proForma ? fmtUsd(proForma.brand_period_cash_impact) : "$0.00"}</div>

          {proForma && (
            <>
              <div className="flex justify-between label-caps mb-2">
                <span>Queue Progress</span>
                <span>
                  {proForma.queue_progress.approved} / {proForma.queue_progress.total}
                </span>
              </div>
              <div className="h-2 bg-obsidian border border-outline mb-6">
                <div
                  className="h-full bg-fire"
                  style={{
                    width: `${(proForma.queue_progress.approved / Math.max(proForma.queue_progress.total, 1)) * 100}%`,
                  }}
                />
              </div>
              <div className="space-y-2 py-4 border-y border-outline mb-6 text-sm">
                {proForma.by_location.map((loc) => (
                  <div key={loc.location_id} className="flex justify-between data-num">
                    <span className="font-body text-on-surface-variant">{loc.location_name}</span>
                    <span>{fmtUsd(loc.period_cash_impact)}</span>
                  </div>
                ))}
              </div>
            </>
          )}

          <button
            className="w-full border border-fire text-fire label-caps py-3 hover:bg-fire/10"
            onClick={() => downloadAuthorized(api.exportChecklistXlsxUrl(), "margin-iq-implementation-checklist.xlsx")}
          >
            Export Checklist
          </button>
        </div>
      </aside>
    </div>
  );
}
