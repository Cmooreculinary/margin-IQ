import { useCallback, useEffect, useState } from "react";
import { api, DriveFile, DriveImportResult, Location, ScanRecord } from "../lib/api";

const TARGET_LABELS: Record<ScanRecord["target"], string> = {
  financials: "Reported Financials",
  menu_item: "Menu Item",
  labor_matrix: "Labor Matrix",
  pmix_row: "PMIX Row",
  competitor: "Competitor Price",
};

const TARGET_FIELDS: Record<ScanRecord["target"], string[]> = {
  financials: ["period_start", "period_end", "gross_sales", "food_cost_actual", "labor_cost_actual"],
  menu_item: ["plu", "name", "category", "price", "recipe_food_cost", "packaging_cost", "daypart"],
  labor_matrix: ["daypart", "hours", "blended_rate"],
  pmix_row: ["plu", "item_name", "period_start", "period_end", "units_sold", "gross_revenue"],
  competitor: ["competitor_name", "item_name", "price", "address"],
};

const NEEDS_LOCATION: ScanRecord["target"][] = ["financials", "labor_matrix", "pmix_row", "competitor"];

const MIME_ICONS: Record<string, string> = {
  "application/pdf": "PDF",
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "XLSX",
  "application/vnd.ms-excel": "XLS",
  "application/vnd.ms-excel.sheet.macroEnabled.12": "XLSM",
  "application/vnd.google-apps.spreadsheet": "Sheet",
  "application/vnd.google-apps.folder": "Folder",
  "image/png": "PNG",
  "image/jpeg": "JPG",
  "image/gif": "GIF",
  "image/webp": "WebP",
};

interface ReviewRow extends ScanRecord {
  include: boolean;
  locationId: string;
}

interface BreadcrumbItem {
  id: string | null;
  name: string;
}

export function DriveImportPage() {
  const [connected, setConnected] = useState<boolean | null>(null);
  const [files, setFiles] = useState<DriveFile[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [breadcrumbs, setBreadcrumbs] = useState<BreadcrumbItem[]>([{ id: null, name: "My Drive" }]);
  const [loading, setLoading] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [scanResults, setScanResults] = useState<DriveImportResult[]>([]);
  const [reviewRows, setReviewRows] = useState<ReviewRow[]>([]);
  const [locations, setLocations] = useState<Location[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [committed, setCommitted] = useState<Record<string, number> | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearching, setIsSearching] = useState(false);

  useEffect(() => {
    api.driveStatus().then((r) => setConnected(r.connected)).catch(() => setConnected(false));
    api.listLocations().then(setLocations);
    const params = new URLSearchParams(window.location.search);
    if (params.get("connected") === "1") {
      setConnected(true);
      window.history.replaceState({}, "", "/drive-import");
    }
  }, []);

  const loadFolder = useCallback(
    async (folderId?: string) => {
      setLoading(true);
      setError(null);
      setIsSearching(false);
      setSearchQuery("");
      try {
        const result = await api.driveFiles(folderId);
        setFiles(result.files);
        setSelected(new Set());
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    if (connected) loadFolder();
  }, [connected, loadFolder]);

  const navigateToFolder = (folder: DriveFile) => {
    setBreadcrumbs((prev) => [...prev, { id: folder.id, name: folder.name }]);
    loadFolder(folder.id);
  };

  const navigateToBreadcrumb = (index: number) => {
    setBreadcrumbs((prev) => prev.slice(0, index + 1));
    const target = breadcrumbs[index];
    loadFolder(target.id ?? undefined);
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setLoading(true);
    setError(null);
    setIsSearching(true);
    try {
      const result = await api.driveSearch(searchQuery.trim());
      setFiles(result.files);
      setSelected(new Set());
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  const toggleSelect = (fileId: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(fileId)) next.delete(fileId);
      else next.add(fileId);
      return next;
    });
  };

  const selectAllImportable = () => {
    const importable = files.filter((f) => f.importable && !f.isFolder).map((f) => f.id);
    setSelected(new Set(importable));
  };

  const handleConnect = async () => {
    try {
      const { auth_url } = await api.driveConnect();
      window.location.href = auth_url;
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };

  const handleDisconnect = async () => {
    await api.driveDisconnect();
    setConnected(false);
    setFiles([]);
    setScanResults([]);
    setReviewRows([]);
  };

  const handleImport = async () => {
    const selectedFiles = files.filter((f) => selected.has(f.id) && !f.isFolder);
    if (selectedFiles.length === 0) return;

    setScanning(true);
    setError(null);
    setScanResults([]);
    setReviewRows([]);
    setCommitted(null);

    try {
      const { results } = await api.driveImportBatch(
        selectedFiles.map((f) => ({ file_id: f.id, file_name: f.name }))
      );
      setScanResults(results);
      const defaultLocation = locations[0]?._id ?? "";
      const rows: ReviewRow[] = [];
      for (const result of results) {
        if (result.error || !result.records) continue;
        for (const r of result.records) {
          const hint = String(r.data.location_hint ?? "").toLowerCase();
          const match = hint
            ? locations.find(
                (l) => l.name.toLowerCase().includes(hint) || hint.includes(l.name.toLowerCase())
              )
            : undefined;
          rows.push({ ...r, include: true, locationId: match?._id ?? defaultLocation });
        }
      }
      setReviewRows(rows);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setScanning(false);
    }
  };

  const commit = async () => {
    setScanning(true);
    setError(null);
    try {
      const records: ScanRecord[] = reviewRows
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
      setScanResults([]);
      setReviewRows([]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setScanning(false);
    }
  };

  const includedCount = reviewRows.filter((r) => r.include).length;
  const selectedFileCount = files.filter((f) => selected.has(f.id) && !f.isFolder).length;

  // Not yet loaded
  if (connected === null) {
    return (
      <div className="max-w-6xl mx-auto px-4 py-8">
        <p className="opacity-60">Checking Google Drive connection...</p>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-8 space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-3xl uppercase tracking-wider">Google Drive Import</h1>
          <p className="text-sm opacity-70 mt-1">
            Connect your Google Drive to import invoices, order guides, and price comparisons directly.
            Files are scanned by AI and you review before anything is saved.
          </p>
        </div>
        {connected && (
          <button
            onClick={handleDisconnect}
            className="border border-outline text-sm label-caps px-4 py-1.5 hover:border-dog hover:text-dog transition-colors"
          >
            Disconnect
          </button>
        )}
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

      {!connected ? (
        <div className="border-2 border-dashed border-outline rounded p-10 text-center space-y-4">
          <p className="label-caps">Connect Google Drive to get started</p>
          <p className="text-sm opacity-60">
            We'll request read-only access to browse and import your distributor files.
          </p>
          <button
            onClick={handleConnect}
            className="border border-fire text-fire label-caps px-6 py-2 hover:bg-fire hover:text-obsidian transition-colors"
          >
            Connect Google Drive
          </button>
        </div>
      ) : (
        <>
          {/* Search bar */}
          <div className="flex gap-2">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSearch()}
              placeholder="Search files by name..."
              className="flex-1 bg-transparent border border-outline px-3 py-2 text-sm focus:border-fire outline-none"
            />
            <button
              onClick={handleSearch}
              disabled={!searchQuery.trim()}
              className="border border-outline label-caps px-4 py-2 text-sm hover:border-fire transition-colors disabled:opacity-40"
            >
              Search
            </button>
          </div>

          {/* Breadcrumbs */}
          {!isSearching && (
            <nav className="flex items-center gap-1 text-sm flex-wrap">
              {breadcrumbs.map((crumb, i) => (
                <span key={i} className="flex items-center gap-1">
                  {i > 0 && <span className="opacity-40">/</span>}
                  <button
                    onClick={() => navigateToBreadcrumb(i)}
                    className={`hover:text-fire transition-colors ${
                      i === breadcrumbs.length - 1 ? "text-fire" : "opacity-70"
                    }`}
                  >
                    {crumb.name}
                  </button>
                </span>
              ))}
            </nav>
          )}
          {isSearching && (
            <div className="flex items-center gap-2 text-sm">
              <span className="opacity-60">Search results for "{searchQuery}"</span>
              <button
                onClick={() => {
                  setIsSearching(false);
                  setSearchQuery("");
                  const last = breadcrumbs[breadcrumbs.length - 1];
                  loadFolder(last.id ?? undefined);
                }}
                className="text-fire hover:underline"
              >
                Back to folder
              </button>
            </div>
          )}

          {/* File list */}
          {loading ? (
            <p className="text-sm opacity-60 py-4">Loading files...</p>
          ) : files.length === 0 ? (
            <p className="text-sm opacity-60 py-4">No files found.</p>
          ) : (
            <>
              <div className="flex items-center gap-3 text-sm">
                <button onClick={selectAllImportable} className="text-fire hover:underline">
                  Select all importable
                </button>
                {selectedFileCount > 0 && (
                  <button onClick={() => setSelected(new Set())} className="opacity-60 hover:opacity-100">
                    Clear selection
                  </button>
                )}
                <span className="opacity-60">{selectedFileCount} file{selectedFileCount !== 1 ? "s" : ""} selected</span>
              </div>

              <div className="border border-outline divide-y divide-outline/50">
                {files.map((file) => (
                  <div
                    key={file.id}
                    className={`flex items-center gap-3 px-3 py-2 text-sm transition-colors ${
                      file.isFolder ? "cursor-pointer hover:bg-surface" : ""
                    } ${selected.has(file.id) ? "bg-fire/5" : ""}`}
                    onClick={() => file.isFolder && navigateToFolder(file)}
                  >
                    {!file.isFolder && (
                      <input
                        type="checkbox"
                        checked={selected.has(file.id)}
                        disabled={!file.importable}
                        onChange={(e) => {
                          e.stopPropagation();
                          toggleSelect(file.id);
                        }}
                        onClick={(e) => e.stopPropagation()}
                        className="shrink-0"
                      />
                    )}
                    {file.isFolder && <span className="w-4 text-center opacity-60">+</span>}

                    <span
                      className={`label-caps text-xs px-1.5 py-0.5 border shrink-0 ${
                        file.isFolder
                          ? "border-fire/40 text-fire"
                          : file.importable
                            ? "border-star/40 text-star"
                            : "border-outline text-on-surface/50"
                      }`}
                    >
                      {MIME_ICONS[file.mimeType] ?? "File"}
                    </span>

                    <span className={`flex-1 truncate ${file.isFolder ? "text-fire" : ""}`}>
                      {file.name}
                    </span>

                    {file.modifiedTime && (
                      <span className="opacity-40 text-xs shrink-0">
                        {new Date(file.modifiedTime).toLocaleDateString()}
                      </span>
                    )}

                    {file.size && (
                      <span className="opacity-40 text-xs shrink-0 w-16 text-right">
                        {formatSize(Number(file.size))}
                      </span>
                    )}
                  </div>
                ))}
              </div>

              {selectedFileCount > 0 && (
                <button
                  onClick={handleImport}
                  disabled={scanning}
                  className="border border-fire text-fire label-caps px-6 py-2 hover:bg-fire hover:text-obsidian transition-colors disabled:opacity-40"
                >
                  {scanning
                    ? "Scanning files..."
                    : `Scan ${selectedFileCount} File${selectedFileCount !== 1 ? "s" : ""}`}
                </button>
              )}
            </>
          )}

          {/* Scan results summary */}
          {scanResults.length > 0 && (
            <div className="space-y-2">
              <h2 className="label-caps text-fire">Scan Results</h2>
              {scanResults.map((result, i) => (
                <div key={i} className="border border-outline p-3 text-sm">
                  <div className="flex items-center gap-3">
                    <span className="font-medium">{result.filename}</span>
                    {result.error ? (
                      <span className="text-dog">{result.error}</span>
                    ) : (
                      <span className="label-caps text-fire text-xs">
                        {result.document_type?.replace(/_/g, " ")}
                      </span>
                    )}
                  </div>
                  {result.summary && <p className="opacity-70 mt-1">{result.summary}</p>}
                  {result.warnings && result.warnings.length > 0 && (
                    <ul className="mt-1 text-fire list-disc list-inside">
                      {result.warnings.map((w, j) => (
                        <li key={j}>{w}</li>
                      ))}
                    </ul>
                  )}
                  {result.records && (
                    <span className="opacity-50 text-xs">{result.records.length} records extracted</span>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Review table */}
          {reviewRows.length > 0 && (
            <div className="space-y-4">
              <h2 className="label-caps text-fire">Review Extracted Records</h2>
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
                    {reviewRows.map((row, idx) => (
                      <tr key={idx} className="border-b border-outline/50 align-top">
                        <td className="p-2">
                          <input
                            type="checkbox"
                            checked={row.include}
                            onChange={(e) =>
                              setReviewRows((rs) =>
                                rs.map((r, i) => (i === idx ? { ...r, include: e.target.checked } : r))
                              )
                            }
                          />
                        </td>
                        <td className="p-2 whitespace-nowrap">{TARGET_LABELS[row.target]}</td>
                        <td className="p-2">
                          <select
                            className="bg-transparent border border-outline p-1"
                            value={row.locationId}
                            onChange={(e) =>
                              setReviewRows((rs) =>
                                rs.map((r, i) => (i === idx ? { ...r, locationId: e.target.value } : r))
                              )
                            }
                          >
                            {row.target === "menu_item" && <option value="">Brand-wide</option>}
                            {locations.map((l) => (
                              <option key={l._id} value={l._id}>
                                {l.name}
                              </option>
                            ))}
                          </select>
                          {row.data.location_hint != null && (
                            <div className="text-xs opacity-60 mt-1">
                              doc says: {String(row.data.location_hint)}
                            </div>
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
                disabled={scanning || includedCount === 0}
                className="border border-fire text-fire label-caps px-6 py-2 hover:bg-fire hover:text-obsidian transition-colors disabled:opacity-40"
              >
                {scanning ? "Committing..." : `Commit ${includedCount} Record${includedCount === 1 ? "" : "s"}`}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
