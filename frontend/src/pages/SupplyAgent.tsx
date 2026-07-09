import { useEffect, useState } from "react";
import { api, SupplyCatalogItem, SupplyComparisonRow, SupplySummary } from "../lib/api";
import { KpiCard } from "../components/KpiCard";

const fmtUsd = (n: number) => `$${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
const fmtUnitPrice = (n: number | null) => (n === null ? "-" : `$${n.toFixed(4)}`);

const TRUSTED = new Set(["High", "Review"]);

function ConfidenceBadge({ confidence }: { confidence: string }) {
  const trusted = TRUSTED.has(confidence);
  const color = confidence === "High" ? "text-star" : trusted ? "text-fire" : "text-on-surface-variant";
  return <span className={`label-caps ${color}`}>{confidence}</span>;
}

function CheaperBadge({ cheaper }: { cheaper: string }) {
  if (cheaper === "US Foods") return <span className="label-caps text-fire">US Foods</span>;
  if (cheaper === "Shamrock") return <span className="label-caps text-star">Shamrock</span>;
  if (cheaper === "Tie") return <span className="label-caps text-on-surface-variant">Tie</span>;
  return <span className="label-caps text-on-surface-variant">Needs review</span>;
}

function groupByCategory(items: SupplyCatalogItem[]): [string, SupplyCatalogItem[]][] {
  const groups = new Map<string, SupplyCatalogItem[]>();
  for (const item of items) {
    const key = item.category ?? "Uncategorized";
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(item);
  }
  return [...groups.entries()];
}

export function SupplyAgentPage() {
  const [rows, setRows] = useState<SupplyComparisonRow[]>([]);
  const [summary, setSummary] = useState<SupplySummary | null>(null);
  const [trustedOnly, setTrustedOnly] = useState(true);
  const [cheaperFilter, setCheaperFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [shoreline, setShoreline] = useState<SupplyCatalogItem[]>([]);
  const [showShoreline, setShowShoreline] = useState(false);

  useEffect(() => {
    api.supplySummary().then(setSummary);
    api.supplyCatalog({ supplier: "Shoreline" }).then(setShoreline);
  }, []);

  useEffect(() => {
    setLoading(true);
    api
      .supplyComparisons({ trusted_only: trustedOnly, cheaper_supplier: cheaperFilter || undefined })
      .then(setRows)
      .finally(() => setLoading(false));
  }, [trustedOnly, cheaperFilter]);

  return (
    <div className="p-6 max-w-[1440px] mx-auto">
      <div className="flex flex-wrap items-end justify-between gap-4 mb-2">
        <h1 className="text-3xl uppercase">Supply Agent</h1>
      </div>
      <p className="label-caps mb-8">
        US Foods vs Shamrock order guide | {summary?.total_items ?? "-"} items compared | Weak matches are hidden by
        default -- verify before switching vendors on any line
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <KpiCard label="Items Compared" value={summary ? String(summary.total_items) : "-"} />
        <KpiCard
          label="Trusted Comparisons"
          value={summary ? String(summary.trusted_comparisons) : "-"}
          delta={summary ? `${summary.needs_review} need review` : undefined}
        />
        <KpiCard
          label="Shamrock Cheaper (Trusted)"
          value={summary ? String(summary.by_cheaper_supplier["Shamrock"] ?? 0) : "-"}
        />
        <KpiCard
          label="Illustrative Switching Savings"
          value={summary ? fmtUsd(summary.illustrative_switching_savings) : "-"}
          highlight
        />
      </div>

      <div className="flex flex-wrap items-center gap-3 mb-4">
        <button
          className={`label-caps px-3 py-2 border ${
            trustedOnly ? "border-fire text-fire bg-fire/10" : "border-outline text-on-surface-variant"
          }`}
          onClick={() => setTrustedOnly((v) => !v)}
        >
          {trustedOnly ? "Showing: High / Review confidence" : "Showing: All matches (incl. weak)"}
        </button>
        <select
          className="bg-obsidian border border-outline px-3 py-2 label-caps"
          value={cheaperFilter}
          onChange={(e) => setCheaperFilter(e.target.value)}
        >
          <option value="">All suppliers</option>
          <option value="US Foods">Cheaper: US Foods</option>
          <option value="Shamrock">Cheaper: Shamrock</option>
          <option value="Tie">Tie</option>
        </select>
      </div>

      <div className="border border-outline bg-surface p-5 overflow-x-auto">
        <table className="w-full text-left border-collapse min-w-[960px]">
          <thead className="label-caps border-b border-outline">
            <tr>
              <th className="py-2">Item (US Foods)</th>
              <th className="py-2">Matched Item (Shamrock)</th>
              <th className="py-2 text-right">US $/unit</th>
              <th className="py-2 text-right">Shamrock $/unit</th>
              <th className="py-2 text-right">Diff %</th>
              <th className="py-2">Cheaper</th>
              <th className="py-2">Confidence</th>
            </tr>
          </thead>
          <tbody className="data-num text-sm">
            {loading ? (
              <tr>
                <td className="py-4 text-on-surface-variant" colSpan={7}>
                  Loading...
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td className="py-4 text-on-surface-variant" colSpan={7}>
                  No comparisons match this filter.
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={row._id} className="border-b border-outline/40 align-top">
                  <td className="py-1.5 font-body">
                    <div>{row.us_description}</div>
                    <div className="label-caps text-on-surface-variant">
                      {row.us_pack} | #{row.us_product_number}
                    </div>
                  </td>
                  <td className="py-1.5 font-body">
                    <div>{row.shamrock_description}</div>
                    <div className="label-caps text-on-surface-variant">
                      {row.shamrock_pack} {row.shamrock_brand ? `| ${row.shamrock_brand}` : ""} | #
                      {row.shamrock_product_number}
                    </div>
                  </td>
                  <td className="py-1.5 text-right">{fmtUnitPrice(row.us_dollar_per_unit)}</td>
                  <td className="py-1.5 text-right">{fmtUnitPrice(row.shamrock_dollar_per_unit)}</td>
                  <td
                    className={`py-1.5 text-right ${
                      row.diff_pct === null ? "text-on-surface-variant" : row.diff_pct < 0 ? "text-star" : "text-dog"
                    }`}
                  >
                    {row.diff_pct === null ? "-" : `${row.diff_pct > 0 ? "+" : ""}${row.diff_pct.toFixed(1)}%`}
                  </td>
                  <td className="py-1.5">
                    <CheaperBadge cheaper={row.cheaper_supplier} />
                  </td>
                  <td className="py-1.5">
                    <ConfidenceBadge confidence={row.match_confidence} />
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="border border-outline bg-surface p-5 mt-8">
        <button className="flex items-center justify-between w-full text-left" onClick={() => setShowShoreline((v) => !v)}>
          <div>
            <h2 className="label-caps text-fire">Shoreline -- {shoreline.length} items (reference catalog)</h2>
            <p className="text-sm text-on-surface-variant mt-1">
              Shoreline supplies disposables, syrups, and coffee-bar items -- a different product mix than the
              US Foods / Shamrock food comparison, so there's no valid item-for-item price match. Listed here for
              reference only.
            </p>
          </div>
          <span className="label-caps text-fire ml-4 whitespace-nowrap">{showShoreline ? "Hide" : "Show"}</span>
        </button>

        {showShoreline && (
          <div className="mt-5 overflow-x-auto">
            {groupByCategory(shoreline).map(([category, items]) => (
              <div key={category} className="mb-6">
                <h3 className="label-caps text-on-surface-variant mb-2">{category}</h3>
                <table className="w-full text-left border-collapse min-w-[720px]">
                  <thead className="label-caps border-b border-outline">
                    <tr>
                      <th className="py-1.5">Product</th>
                      <th className="py-1.5">Packaging</th>
                      <th className="py-1.5">Code</th>
                      <th className="py-1.5 text-right">Price</th>
                    </tr>
                  </thead>
                  <tbody className="data-num text-sm">
                    {items.map((item) => (
                      <tr key={item._id} className="border-b border-outline/40">
                        <td className="py-1.5 font-body">{item.product}</td>
                        <td className="py-1.5">{item.packaging ?? "-"}</td>
                        <td className="py-1.5">{item.code ?? "-"}</td>
                        <td className="py-1.5 text-right">{item.price_raw ?? "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
