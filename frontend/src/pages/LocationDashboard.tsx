import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, LocationDashboard as LocationDashboardData } from "../lib/api";
import { KpiCard } from "../components/KpiCard";

const fmtUsd = (n: number) => `$${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
const fmtPct = (n: number) => `${(n * 100).toFixed(1)}%`;

const QUADRANT_COLORS: Record<string, string> = {
  star: "bg-star",
  plowhorse: "bg-plowhorse",
  puzzle: "bg-puzzle",
  dog: "bg-dog",
};

export function LocationDashboardPage() {
  const { locationId } = useParams<{ locationId: string }>();
  const [data, setData] = useState<LocationDashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!locationId) return;
    api.locationDashboard(locationId).then(setData).catch((e) => setError(String(e)));
  }, [locationId]);

  if (error) return <div className="p-6 text-error">{error}</div>;
  if (!data) return <div className="p-6 label-caps">Loading location dashboard…</div>;

  return (
    <div className="p-6 max-w-[1440px] mx-auto">
      <h1 className="text-3xl mb-6 uppercase">{data.name}</h1>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <KpiCard label="Location Revenue" value={fmtUsd(data.revenue)} />
        <KpiCard label="Prime Cost %" value={fmtPct(data.prime_cost_pct)} />
        <KpiCard label="Labor Allocation %" value={fmtPct(data.labor_allocation_pct)} />
        <KpiCard label="Items Analyzed" value={String(data.items_analyzed)} />
      </div>

      <h2 className="text-xl mb-4 uppercase text-fire">Quadrant Mix</h2>
      <div className="w-full h-6 bg-surface border border-outline flex mb-8 overflow-hidden">
        {Object.entries(data.quadrant_mix).map(([q, pct]) => (
          <div key={q} className={QUADRANT_COLORS[q]} style={{ width: `${pct * 100}%` }} title={`${q}: ${(pct * 100).toFixed(0)}%`} />
        ))}
      </div>
      <div className="flex gap-6 mb-10 label-caps">
        {Object.entries(data.quadrant_mix).map(([q, pct]) => (
          <span key={q} className="flex items-center gap-2">
            <span className={`w-2 h-2 ${QUADRANT_COLORS[q]}`} /> {q} {(pct * 100).toFixed(0)}%
          </span>
        ))}
      </div>

      <h2 className="text-xl mb-4 uppercase text-fire">Category Performance</h2>
      <table className="w-full text-left border-collapse">
        <thead className="border-b border-outline label-caps">
          <tr>
            <th className="py-2">Category</th>
            <th className="py-2 text-right">Revenue</th>
            <th className="py-2 text-right">Prime Cost %</th>
            <th className="py-2 text-right">CM$</th>
            <th className="py-2 text-right">CM%</th>
            <th className="py-2 text-right">Items</th>
          </tr>
        </thead>
        <tbody className="data-num text-sm">
          {data.category_performance.map((row) => (
            <tr key={row.category} className="border-b border-outline/50">
              <td className="py-2 font-body">{row.category}</td>
              <td className="py-2 text-right">{fmtUsd(row.revenue)}</td>
              <td className="py-2 text-right">{fmtPct(row.prime_cost_pct)}</td>
              <td className="py-2 text-right">{fmtUsd(row.cm_dollars)}</td>
              <td className="py-2 text-right">{fmtPct(row.cm_pct)}</td>
              <td className="py-2 text-right">{row.item_count}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
