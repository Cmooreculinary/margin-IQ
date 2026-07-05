// Dev: "/api" is proxied to the backend by Vite (see vite.config.ts).
// Production (single combined service): the API is same-origin at root, so the
// Render build sets VITE_API_BASE="" .
const BASE_URL = import.meta.env.VITE_API_BASE ?? "/api";
const TOKEN_STORAGE_KEY = "margin_iq_tenant_token";
export const DEMO_TENANT_TOKEN = "snakes-lattes-demo-token";
const LEGACY_DEMO_TOKENS = new Set(["rook-roast-demo-token"]);

export function getTenantToken(): string {
  const stored = localStorage.getItem(TOKEN_STORAGE_KEY);
  return stored && !LEGACY_DEMO_TOKENS.has(stored) ? stored : DEMO_TENANT_TOKEN;
}

export function setTenantToken(token: string) {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${getTenantToken()}`,
      ...(options.headers || {}),
    },
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json() as Promise<T>;
}

function qs(params: Record<string, string | number | boolean | undefined>): string {
  const usable = Object.entries(params).filter(([, v]) => v !== undefined) as [string, string | number | boolean][];
  return usable.length ? `?${new URLSearchParams(usable.map(([k, v]) => [k, String(v)])).toString()}` : "";
}

export interface Location {
  _id: string;
  name: string;
  code: string;
  sqft?: number;
  concept_notes?: string;
}

export interface ItemRow {
  plu: string;
  name: string;
  category: string;
  daypart: string;
  location_id: string;
  location_name: string;
  units_sold: number;
  price: number;
  food_cost: number;
  labor_cost: number;
  packaging_cost: number;
  revenue: number;
  prime_cost_pct: number;
  food_cost_pct: number;
  cm_dollars: number;
  cm_pct: number;
  quadrant: "star" | "plowhorse" | "puzzle" | "dog";
  is_food_cost_mirage: boolean;
}

export interface Recommendation {
  _id: string;
  plu: string;
  name: string;
  type: "price" | "reposition" | "bundle" | "kill" | "reengineer" | "daypart_shift";
  quadrant: string;
  current_price: number;
  recommended_price: number | null;
  rationale: string;
  projected_bps_lift: number | null;
  pmix_offset_pct: number | null;
  projected_cash_lift: number | null;
  location_id: string;
  location_name: string;
  status: "pending" | "approved" | "modified" | "denied";
  final_price: number | null;
  created_at: string;
}

export interface ProForma {
  brand_period_cash_impact: number;
  brand_annualized_cash_impact: number;
  queue_progress: { approved: number; pending: number; denied: number; total: number };
  by_location: {
    location_id: string;
    location_name: string;
    period_cash_impact: number;
    annualized_cash_impact: number;
    approved_recommendation_count: number;
  }[];
}

export interface BrandDashboard {
  combined_revenue: number;
  blended_prime_cost_pct: number;
  combined_cm_dollars: number;
  projected_bps_lift: number;
  approved_cash_flow_impact: number;
  locations: Array<Record<string, unknown>>;
  pro_forma: ProForma;
}

export interface LocationDashboard {
  location_id: string;
  name: string;
  revenue: number;
  prime_cost_pct: number;
  labor_allocation_pct: number;
  items_analyzed: number;
  quadrant_mix: Record<string, number>;
  category_performance: Array<{ category: string; revenue: number; prime_cost_pct: number; cm_dollars: number; cm_pct: number; item_count: number }>;
}

export interface BaselineInfo {
  location_id: string;
  signed_by: string;
  locked_at: string;
  revenue: number;
  cm_total: number;
  cm_pct: number;
  item_count: number;
}

export interface ValidationResult {
  measured_at: string;
  assumptions: { seasonal_index_baseline: number; seasonal_index_post: number; food_inflation_pct: number };
  baseline: { revenue: number; cm_total: number; cm_pct: number };
  actual: { revenue: number; cm_total: number; cm_pct: number };
  bridge: {
    baseline_cm: number;
    seasonality_effect: number;
    inflation_effect: number;
    price_effect: number;
    pmix_volume_effect: number;
    actual_cm: number;
  };
  validated_bps_lift: number;
  offset_pct: number | null;
  item_bridge: {
    plu: string;
    name: string;
    status: "matched" | "new_since_baseline" | "discontinued";
    baseline_cm_total: number;
    actual_cm_total: number | null;
    delta: number | null;
    price_effect: number;
  }[];
}

export interface EngagementPlan {
  tenant: { name: string; slug: string; monitoring_tier?: string };
  plan: {
    brand_name: string;
    proposal_month: string;
    engagement_start: string;
    scope: {
      locations: string[];
      excluded_scope: string[];
      annual_fnb_revenue_estimate: number;
      target_roi_payback_days: number;
      delivery_window: string;
      guardrails: string[];
    };
    timeline: {
      phase: string;
      name: string;
      timing: string;
      needs: string[];
      deliverables: string[];
    }[];
    data_requirements: string[];
    deliverables: { name: string; category: string; status: string }[];
    terms: {
      project_fee: number | string;
      payment_structure: string;
      invoice_1: number | string;
      invoice_2: number | string;
      delivery_window: string;
      onsite_review: string;
      optional_monitoring: string[];
    };
    franchise_angle: string[];
    calendar?: {
      assumes: string;
      data_checklist: { item: string; due: string; status: "outstanding" | "received" }[];
      milestones: { date: string; name: string; owner: "client" | "ddd" | "both"; type: "milestone" | "deliverable" | "payment" }[];
    };
  };
}

// Demo periods match the seeded Snakes & Lattes dataset.
export const DEMO_PERIOD = { period_start: "2026-04-01T00:00:00", period_end: "2026-06-30T00:00:00" };
export const DEMO_POST_PERIOD = { post_period_start: "2026-10-01T00:00:00", post_period_end: "2026-12-31T00:00:00" };

export const api = {
  listLocations: () => request<Location[]>("/locations"),

  listItems: (locationId: string, filters: Partial<{ category: string; daypart: string; quadrant: string; flagged_only: boolean }> = {}) =>
    request<ItemRow[]>(`/items${qs({ location_id: locationId, ...DEMO_PERIOD, ...filters })}`),

  pareto: (locationId: string, metric: "revenue" | "cm_dollars" = "revenue") =>
    request<{ metric: string; total: number; rows: { plu: string; name: string; value: number; cumulative_pct: number }[]; top_80_pct_plus: string[] }>(
      `/items/pareto${qs({ location_id: locationId, metric, ...DEMO_PERIOD })}`
    ),

  brandDashboard: () => request<BrandDashboard>(`/dashboard/brand${qs(DEMO_PERIOD)}`),

  locationDashboard: (locationId: string) => request<LocationDashboard>(`/dashboard/location/${locationId}${qs(DEMO_PERIOD)}`),

  listRecommendations: (params: Partial<{ location_id: string; status: string }> = {}) =>
    request<Recommendation[]>(`/recommendations${qs(params)}`),

  decideRecommendation: (id: string, status: "approved" | "modified" | "denied", decidedBy: string, finalPrice?: number) =>
    request<Recommendation>(`/recommendations/${id}/decide`, {
      method: "POST",
      body: JSON.stringify({ status, decided_by: decidedBy, final_price: finalPrice }),
    }),

  proForma: () => request<ProForma>("/recommendations/pro-forma"),

  exportItemsXlsxUrl: (locationId: string) => `${BASE_URL}/items/export.xlsx${qs({ location_id: locationId, ...DEMO_PERIOD })}`,
  exportChecklistXlsxUrl: () => `${BASE_URL}/recommendations/export-checklist.xlsx`,
  exportAnalysisDeckUrl: () => `${BASE_URL}/exports/analysis-deck.pdf${qs(DEMO_PERIOD)}`,
  exportRecommendationsDeckUrl: () => `${BASE_URL}/exports/recommendations-deck.pdf${qs(DEMO_PERIOD)}`,

  getBaseline: (locationId: string) => request<BaselineInfo>(`/validation/baseline/${locationId}`),

  lockBaseline: (locationId: string, signedBy: string) =>
    request<BaselineInfo>(`/validation/baseline/lock${qs({ location_id: locationId, ...DEMO_PERIOD })}`, {
      method: "POST",
      body: JSON.stringify({ signed_by: signedBy, acknowledged: true }),
    }),

  measureValidation: (
    locationId: string,
    assumptions: { food_inflation_pct: number; seasonal_index_baseline: number; seasonal_index_post: number }
  ) =>
    request<ValidationResult>(`/validation/measure${qs({ location_id: locationId, ...DEMO_POST_PERIOD })}`, {
      method: "POST",
      body: JSON.stringify(assumptions),
    }),

  listValidationRuns: (locationId?: string) =>
    request<ValidationResult[]>(`/validation/runs${qs({ location_id: locationId })}`),

  engagementPlan: () => request<EngagementPlan>("/engagement/plan"),
};

/** XLSX exports require the tenant bearer token, so a plain <a href> won't
 * carry auth -- fetch as a blob and trigger the download manually. */
export async function downloadAuthorized(url: string, filename: string) {
  const res = await fetch(url, { headers: { Authorization: `Bearer ${getTenantToken()}` } });
  if (!res.ok) throw new Error(`Export failed: ${res.status}`);
  const blob = await res.blob();
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(objectUrl);
}
