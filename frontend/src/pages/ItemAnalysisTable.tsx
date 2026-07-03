import { useEffect, useMemo, useState } from "react";
import { api, downloadAuthorized, ItemRow, Location } from "../lib/api";
import { QuadrantBadge } from "../components/QuadrantBadge";

const fmtUsd = (n: number) => `$${n.toFixed(2)}`;
const fmtPct = (n: number) => `${(n * 100).toFixed(1)}%`;

export function ItemAnalysisTablePage() {
  const [locations, setLocations] = useState<Location[]>([]);
  const [locationId, setLocationId] = useState<string>("");
  const [items, setItems] = useState<ItemRow[]>([]);
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listLocations().then((locs) => {
      setLocations(locs);
      if (locs.length) setLocationId(locs[0]._id);
    });
  }, []);

  useEffect(() => {
    if (!locationId) return;
    api
      .listItems(locationId, { flagged_only: flaggedOnly })
      .then(setItems)
      .catch((e) => setError(String(e)));
  }, [locationId, flaggedOnly]);

  const sorted = useMemo(() => [...items].sort((a, b) => b.revenue - a.revenue), [items]);

  return (
    <div className="p-6 max-w-[1440px] mx-auto">
      <div className="flex flex-wrap items-end justify-between gap-4 mb-6">
        <h1 className="text-3xl uppercase">Menu Item Analysis</h1>
        <div className="flex items-center gap-3">
          <select
            className="bg-obsidian border border-outline px-3 py-2 label-caps"
            value={locationId}
            onChange={(e) => setLocationId(e.target.value)}
          >
            {locations.map((l) => (
              <option key={l._id} value={l._id}>
                {l.name.toUpperCase()}
              </option>
            ))}
          </select>
          <button
            className={`label-caps px-3 py-2 border ${flaggedOnly ? "border-fire text-fire" : "border-outline"}`}
            onClick={() => setFlaggedOnly((v) => !v)}
          >
            Flagged Only
          </button>
          <button
            className="bg-fire text-obsidian label-caps px-4 py-2 hover:brightness-110"
            onClick={() => locationId && downloadAuthorized(api.exportItemsXlsxUrl(locationId), "margin-iq-item-analysis.xlsx")}
          >
            Export XLSX
          </button>
        </div>
      </div>

      {error && <div className="text-error mb-4">{error}</div>}

      <div className="border border-outline overflow-x-auto">
        <table className="w-full text-left border-collapse min-w-[1100px]">
          <thead className="bg-surface border-b border-outline label-caps">
            <tr>
              <th className="px-3 py-3">Item</th>
              <th className="px-3 py-3">Category</th>
              <th className="px-3 py-3 text-right">Units</th>
              <th className="px-3 py-3 text-right">Price</th>
              <th className="px-3 py-3 text-right">Food Cost</th>
              <th className="px-3 py-3 text-right">Labor</th>
              <th className="px-3 py-3 text-right">Prime %</th>
              <th className="px-3 py-3 text-right">CM$</th>
              <th className="px-3 py-3 text-center">Quadrant</th>
              <th className="px-3 py-3 text-center">Flag</th>
            </tr>
          </thead>
          <tbody className="data-num text-sm">
            {sorted.map((item, idx) => (
              <tr
                key={item.plu}
                className={`border-b border-outline/40 hover:bg-surface-hover hover:outline hover:outline-1 hover:outline-fire ${
                  idx % 2 === 0 ? "bg-surface" : "bg-obsidian"
                } ${item.is_food_cost_mirage ? "outline outline-1 outline-fire/40" : ""}`}
              >
                <td className="px-3 py-2 font-body text-on-surface">{item.name}</td>
                <td className="px-3 py-2 text-on-surface-variant font-body">{item.category}</td>
                <td className="px-3 py-2 text-right">{item.units_sold.toLocaleString()}</td>
                <td className="px-3 py-2 text-right">{fmtUsd(item.price)}</td>
                <td className="px-3 py-2 text-right">{fmtUsd(item.food_cost)}</td>
                <td className="px-3 py-2 text-right">{fmtUsd(item.labor_cost)}</td>
                <td className="px-3 py-2 text-right">{fmtPct(item.prime_cost_pct)}</td>
                <td className="px-3 py-2 text-right">{fmtUsd(item.cm_dollars)}</td>
                <td className="px-3 py-2 text-center">
                  <QuadrantBadge quadrant={item.quadrant} />
                </td>
                <td className="px-3 py-2 text-center">
                  {item.is_food_cost_mirage && (
                    <span className="text-fire" title="Food-cost mirage: strong food margin, weak prime margin">
                      ⚠
                    </span>
                  )}
                </td>
              </tr>
            ))}
            {sorted.length === 0 && (
              <tr>
                <td colSpan={10} className="px-3 py-8 text-center label-caps text-on-surface-variant">
                  No items match this filter.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
