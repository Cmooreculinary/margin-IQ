import { useEffect, useState } from "react";
import { api, BaselineInfo, Location, ValidationResult } from "../lib/api";

const fmtUsd = (n: number) =>
  `${n < 0 ? "-" : "+"}$${Math.abs(n).toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
const fmtUsdPlain = (n: number) => `$${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;

function BridgeRow({ label, value, isAnchor = false }: { label: string; value: number; isAnchor?: boolean }) {
  const color = isAnchor ? "text-on-surface" : value >= 0 ? "text-star" : "text-dog";
  return (
    <div className={`flex justify-between py-2 ${isAnchor ? "border-y border-outline font-bold" : ""}`}>
      <span className="label-caps">{label}</span>
      <span className={`data-num ${color}`}>{isAnchor ? fmtUsdPlain(value) : fmtUsd(value)}</span>
    </div>
  );
}

export function ValidationPage() {
  const [locations, setLocations] = useState<Location[]>([]);
  const [locationId, setLocationId] = useState("");
  const [baseline, setBaseline] = useState<BaselineInfo | null>(null);
  const [result, setResult] = useState<ValidationResult | null>(null);
  const [inflationPct, setInflationPct] = useState("3.0");
  const [seasonBaseline, setSeasonBaseline] = useState("1.10");
  const [seasonPost, setSeasonPost] = useState("0.90");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.listLocations().then((locs) => {
      setLocations(locs);
      if (locs.length) setLocationId(locs[0]._id);
    });
  }, []);

  useEffect(() => {
    if (!locationId) return;
    setBaseline(null);
    setResult(null);
    setError(null);
    api.getBaseline(locationId).then(setBaseline).catch(() => setBaseline(null));
    api
      .listValidationRuns(locationId)
      .then((runs) => setResult(runs[0] ?? null))
      .catch(() => setResult(null));
  }, [locationId]);

  const lock = async () => {
    setBusy(true);
    setError(null);
    try {
      const locked = await api.lockBaseline(locationId, "demo-operator");
      setBaseline(locked);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const measure = async () => {
    setBusy(true);
    setError(null);
    try {
      const r = await api.measureValidation(locationId, {
        food_inflation_pct: parseFloat(inflationPct) / 100,
        seasonal_index_baseline: parseFloat(seasonBaseline),
        seasonal_index_post: parseFloat(seasonPost),
      });
      setResult(r);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="p-6 max-w-[1440px] mx-auto">
      <div className="flex flex-wrap items-end justify-between gap-4 mb-2">
        <h1 className="text-3xl uppercase">Validation</h1>
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
      </div>
      <p className="label-caps mb-8">
        Baseline: Q1 2026 (Peak Season) · Post-implementation: Q2 2026 · Validated results only — projections live elsewhere
      </p>

      {error && <div className="text-error mb-4 text-sm break-all">{error}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-8">
        {/* Baseline lock */}
        <div className="border border-outline bg-surface p-5">
          <h2 className="label-caps text-fire mb-4">1 · Baseline Lock</h2>
          {baseline ? (
            <>
              <p className="data-num text-2xl mb-2">{fmtUsdPlain(baseline.cm_total)}</p>
              <p className="label-caps mb-1">Locked CM$ · {baseline.item_count} items</p>
              <p className="label-caps text-on-surface-variant">
                Signed by {baseline.signed_by} · {new Date(baseline.locked_at).toLocaleDateString()}
              </p>
              <p className="label-caps text-star mt-3">LOCKED — IMMUTABLE</p>
            </>
          ) : (
            <>
              <p className="text-sm text-on-surface-variant mb-4">
                Locking snapshots the season-matched 90-day baseline. This is the digital
                sign-off your post-implementation results will be measured against. It cannot
                be edited afterward.
              </p>
              <button
                className="w-full bg-fire text-obsidian label-caps py-3 hover:brightness-110 disabled:opacity-40"
                onClick={lock}
                disabled={busy || !locationId}
              >
                Acknowledge &amp; Lock Q1 Baseline
              </button>
            </>
          )}
        </div>

        {/* Measurement assumptions */}
        <div className="border border-outline bg-surface p-5">
          <h2 className="label-caps text-fire mb-4">2 · Measurement Assumptions</h2>
          <label className="label-caps block mb-1">Documented Food Inflation %</label>
          <input
            className="w-full bg-obsidian border border-outline px-3 py-2 data-num mb-3"
            value={inflationPct}
            onChange={(e) => setInflationPct(e.target.value)}
          />
          <div className="grid grid-cols-2 gap-3 mb-4">
            <div>
              <label className="label-caps block mb-1">Season Idx (Baseline)</label>
              <input
                className="w-full bg-obsidian border border-outline px-3 py-2 data-num"
                value={seasonBaseline}
                onChange={(e) => setSeasonBaseline(e.target.value)}
              />
            </div>
            <div>
              <label className="label-caps block mb-1">Season Idx (Post)</label>
              <input
                className="w-full bg-obsidian border border-outline px-3 py-2 data-num"
                value={seasonPost}
                onChange={(e) => setSeasonPost(e.target.value)}
              />
            </div>
          </div>
          <button
            className="w-full border border-fire text-fire label-caps py-3 hover:bg-fire/10 disabled:opacity-40"
            onClick={measure}
            disabled={busy || !baseline}
          >
            {baseline ? "Measure Q2 vs Baseline" : "Lock a baseline first"}
          </button>
        </div>

        {/* Headline results */}
        <div className={`border p-5 ${result ? "border-fire shadow-glow bg-surface" : "border-outline bg-surface"}`}>
          <h2 className="label-caps text-fire mb-4">3 · Validated Results</h2>
          {result ? (
            <>
              <p className="label-caps mb-1">Validated BPS Lift (CM%)</p>
              <p className={`data-num text-3xl mb-4 ${result.validated_bps_lift >= 0 ? "text-star" : "text-dog"}`}>
                {result.validated_bps_lift >= 0 ? "+" : ""}
                {result.validated_bps_lift.toFixed(0)} BPS
              </p>
              <p className="label-caps mb-1">Offset % of Food Inflation</p>
              <p className="data-num text-2xl text-fire">
                {result.offset_pct !== null ? `${(result.offset_pct * 100).toFixed(0)}%` : "n/a"}
              </p>
            </>
          ) : (
            <p className="text-sm text-on-surface-variant">Run a measurement to see validated lift.</p>
          )}
        </div>
      </div>

      {result && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="border border-outline bg-surface p-5">
            <h2 className="label-caps text-fire mb-4">P&amp;L Bridge — CM$ Baseline → Actual</h2>
            <BridgeRow label="Baseline CM$" value={result.bridge.baseline_cm} isAnchor />
            <BridgeRow label="Seasonality Adjustment" value={result.bridge.seasonality_effect} />
            <BridgeRow label="Food Inflation" value={result.bridge.inflation_effect} />
            <BridgeRow label="Price Moves" value={result.bridge.price_effect} />
            <BridgeRow label="PMIX / Volume" value={result.bridge.pmix_volume_effect} />
            <BridgeRow label="Actual CM$" value={result.bridge.actual_cm} isAnchor />
          </div>

          <div className="border border-outline bg-surface p-5 overflow-x-auto">
            <h2 className="label-caps text-fire mb-4">Item-Level Bridge</h2>
            <table className="w-full text-left border-collapse min-w-[480px]">
              <thead className="label-caps border-b border-outline">
                <tr>
                  <th className="py-2">Item</th>
                  <th className="py-2 text-right">Baseline CM$</th>
                  <th className="py-2 text-right">Actual CM$</th>
                  <th className="py-2 text-right">Δ</th>
                  <th className="py-2 text-right">Price Effect</th>
                </tr>
              </thead>
              <tbody className="data-num text-sm">
                {result.item_bridge
                  .filter((row) => row.status === "matched")
                  .sort((a, b) => (b.delta ?? 0) - (a.delta ?? 0))
                  .map((row) => (
                    <tr key={row.plu} className="border-b border-outline/40">
                      <td className="py-1.5 font-body">{row.name}</td>
                      <td className="py-1.5 text-right">{fmtUsdPlain(row.baseline_cm_total)}</td>
                      <td className="py-1.5 text-right">{fmtUsdPlain(row.actual_cm_total ?? 0)}</td>
                      <td className={`py-1.5 text-right ${(row.delta ?? 0) >= 0 ? "text-star" : "text-dog"}`}>
                        {fmtUsd(row.delta ?? 0)}
                      </td>
                      <td className={`py-1.5 text-right ${row.price_effect > 0 ? "text-fire" : "text-on-surface-variant"}`}>
                        {row.price_effect ? fmtUsd(row.price_effect) : "—"}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
