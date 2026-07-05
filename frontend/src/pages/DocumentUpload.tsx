import { useCallback, useEffect, useRef, useState } from "react";
import { api, Location, ScanRecord, ScanResult, scanDocument } from "../lib/api";

const TARGET_LABELS: Record<ScanRecord["target"], string> = {
  financials: "Reported Financials",
  menu_item: "Menu Item",
  labor_matrix: "Labor Matrix",
  pmix_row: "PMIX Row",
  competitor: "Competitor Price",
};

// Which extracted fields to surface per target in the review table.
const TARGET_FIELDS: Record<ScanRecord["target"], string[]> = {
  financials: ["period_start", "period_end", "gross_sales", "food_cost_actual", "labor_cost_actual"],
  menu_item: ["plu", "name", "category", "price", "recipe_food_cost", "packaging_cost", "daypart"],
  labor_matrix: ["daypart", "hours", "blended_rate"],
  pmix_row: ["plu", "item_name", "period_start", "period_end", "units_sold", "gross_revenue"],
  competitor: ["competitor_name", "item_name", "price", "address"],
};

// Targets that must carry a location_id before commit.
const NEEDS_LOCATION: ScanRecord["target"][] = ["financials", "labor_matrix", "pmix_row", "competitor"];

interface ReviewRow extends ScanRecord {
  include: boolean;
  locationId: string;
}

export function DocumentUploadPage() {
  const [locations, setLocations] = useState<Location[]>([]);
  const [scan, setScan] = useState<ScanResult | null>(null);
  const [rows, setRows] = useState<ReviewRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [committed, setCommitted] = useState<Record<string, number> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.listLocations().then(setLocations);
  }, []);

  const handleFile = useCallback(
    async (file: File) => {
      setBusy(true);
      setError(null);
      setScan(null);
      setCommitted(null);
      try {
        const result = await scanDocument(file);
        setScan(result);
        const defaultLocation = locations[0]?._id ?? "";
        setRows(
          result.records.map((r) => {
            // Pre-select a location if the hint matches one by name.
            const hint = String(r.data.location_hint ?? "").toLowerCase();
            const match = hint ? locations.find((l) => l.name.toLowerCase().includes(hint) || hint.includes(l.name.toLowerCase())) : undefined;
            return { ...r, include: true, locationId: match?._id ?? defaultLocation };
          })
        );
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setBusy(false);
      }
    },
    [locations]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files?.[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  const commit = async () => {
    if (!scan) return;
    setBusy(true);
    setError(null);
    try {
      const records: ScanRecord[] = rows
        .filter((r) => r.include)
        .map((r) => {
          const data = { ...r.data };
          delete data.location_hint;
          if (NEEDS_LOCATION.includes(r.target) || (r.target === "menu_item" && r.locationId)) {
            data.location_id = r.locationId;
          }
          return { target: r.target, data };
        });
      const result = await api.commitScan(records);
      setCommitted(result.committed);
      setScan(null);
      setRows([]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  const includedCount = rows.filter((r) => r.include).length;

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-6">
      <div>
        <h1 className="font-display text-3xl uppercase tracking-wider">Upload Documents</h1>
        <p className="text-sm opacity-70 mt-1">
          Upload a photo, screenshot, or PDF of a P&amp;L, menu, PMIX report, labor schedule, or competitor menu.
          The data is extracted automatically -- nothing is saved until you review and commit it.
        </p>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        className={`border-2 border-dashed rounded p-10 text-center cursor-pointer transition-colors ${
          dragOver ? "border-fire bg-fire/5" : "border-outline hover:border-fire/60"
        }`}
      >
        <input
          ref={inputRef}
          type="file"
          accept="image/png,image/jpeg,image/gif,image/webp,application/pdf"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
            e.target.value = "";
          }}
        />
        <p className="label-caps">{busy ? "Scanning document..." : "Drop a file here or click to browse"}</p>
        <p className="text-xs opacity-60 mt-2">PNG, JPEG, GIF, WebP, or PDF -- up to 20 MB</p>
      </div>

      {error && <div className="border border-dog text-dog p-3 text-sm whitespace-pre-wrap">{error}</div>}

      {committed && (
        <div className="border border-star text-star p-3 text-sm">
          Committed:{" "}
          {Object.entries(committed)
            .map(([t, n]) => `${n} ${TARGET_LABELS[t as ScanRecord["target"]] ?? t}${n === 1 ? "" : "s"}`)
            .join(", ")}
        </div>
      )}

      {scan && (
        <div className="space-y-4">
          <div className="border border-outline p-4">
            <div className="flex items-center gap-3">
              <span className="label-caps text-fire">{scan.document_type.replace(/_/g, " ")}</span>
              {scan.filename && <span className="text-xs opacity-60">{scan.filename}</span>}
            </div>
            <p className="text-sm mt-2">{scan.summary}</p>
            {scan.warnings.length > 0 && (
              <ul className="mt-2 text-sm text-fire list-disc list-inside">
                {scan.warnings.map((w, i) => (
                  <li key={i}>{w}</li>
                ))}
              </ul>
            )}
          </div>

          {rows.length === 0 ? (
            <p className="text-sm opacity-70">No importable records were found in this document.</p>
          ) : (
            <>
              <div className="overflow-x-auto border border-outline">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-outline label-caps text-left">
                      <th className="p-2">Import</th>
                      <th className="p-2">Type</th>
                      <th className="p-2">Location</th>
                      <th className="p-2">Extracted Data</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row, idx) => (
                      <tr key={idx} className="border-b border-outline/50 align-top">
                        <td className="p-2">
                          <input
                            type="checkbox"
                            checked={row.include}
                            onChange={(e) => setRows((rs) => rs.map((r, i) => (i === idx ? { ...r, include: e.target.checked } : r)))}
                          />
                        </td>
                        <td className="p-2 whitespace-nowrap">{TARGET_LABELS[row.target]}</td>
                        <td className="p-2">
                          <select
                            className="bg-transparent border border-outline p-1"
                            value={row.locationId}
                            onChange={(e) => setRows((rs) => rs.map((r, i) => (i === idx ? { ...r, locationId: e.target.value } : r)))}
                          >
                            {row.target === "menu_item" && <option value="">Brand-wide</option>}
                            {locations.map((l) => (
                              <option key={l._id} value={l._id}>
                                {l.name}
                              </option>
                            ))}
                          </select>
                          {row.data.location_hint != null && (
                            <div className="text-xs opacity-60 mt-1">doc says: {String(row.data.location_hint)}</div>
                          )}
                        </td>
                        <td className="p-2">
                          <div className="flex flex-wrap gap-x-4 gap-y-1">
                            {TARGET_FIELDS[row.target]
                              .filter((f) => row.data[f] != null)
                              .map((f) => (
                                <span key={f}>
                                  <span className="opacity-60">{f.replace(/_/g, " ")}:</span>{" "}
                                  <span className="data-num">{String(row.data[f])}</span>
                                </span>
                              ))}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <button
                onClick={commit}
                disabled={busy || includedCount === 0}
                className="border border-fire text-fire label-caps px-6 py-2 hover:bg-fire hover:text-obsidian transition-colors disabled:opacity-40"
              >
                {busy ? "Committing..." : `Commit ${includedCount} Record${includedCount === 1 ? "" : "s"}`}
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
