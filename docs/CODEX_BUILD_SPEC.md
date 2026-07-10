# Margin IQ — Real-Data Build Spec (Codex Handoff)

**Author / reviewing authority:** Lead engineer (Claude session, Margin IQ)
**Implementer:** Codex
**Customer:** Snakes & Lattes Tempe LLC (US Foods customer #54158019, Phoenix division 4146) — contact: Susan
**Return protocol:** Every phase comes back as a PR against `main` for lead + founder approval before merge. Do not self-merge.

---

## 0. The Accuracy Contract (read first, applies to everything below)

This customer is explicitly testing us for **accuracy in all areas**. These rules are not style
preferences; a violation is a failed deliverable.

1. **No invented numbers.** Every figure shown in the app must be traceable to a source document
   in `docs/source/`, a seeded data file in `backend/app/seed/data/`, or arithmetic on those.
   If a number cannot be traced, it does not ship.
2. **No synthetic placeholder data.** Where real data does not exist yet (menu PMIX, financials,
   labor), the page shows an honest empty state that names the missing input — never sample data.
3. **Compute, don't transcribe.** Any derived figure (percentages, savings, premiums) is computed
   at request time or seed time from stored raw values — never hardcoded into copy or JSX.
4. **Verify extraction two ways.** Any number extracted from a PDF must be validated by an
   independent second pass (e.g., re-extract with different parsing, or check row math:
   `qty x unit price = extended price`, column sums = document totals). Mismatches get flagged
   in a `data_quality_flags` collection, not silently corrected.
5. **Label confidence.** Anything below full confidence (fuzzy item matches, OCR of photographed
   invoices) carries a visible confidence tier in the UI. "Weak" data is never aggregated into
   headline KPI numbers.
6. **PDF layout warning (learned the hard way):** the US Foods order guide's text layer wraps and
   interleaves adjacent rows. Naive line-regex parsing mispairs prices across rows. Use
   column-aware extraction (pdfplumber `extract_table`/word positions), then validate every row
   against the known invariants (product # is 6–7 digits, price ends `/CS` or `/EA`, line numbers
   are sequential 1–188).

---

## 1. Current State (what exists, what is real, what is fake)

### Stack
- Backend: FastAPI + Motor (async MongoDB), tenant-scoped bearer auth, all routes under `/api`.
  Entry: `backend/app/main.py`. Seeds run in the lifespan hook when `SEED_DEMO=true`.
- Frontend: React + Vite + TypeScript, pages in `frontend/src/pages/`, API client in
  `frontend/src/lib/api.ts`, nav in `frontend/src/components/TopNav.tsx`.
- Tests: `backend/tests/` on pytest + mongomock-motor (no real Mongo needed).

### REAL data — keep and build on
| Data | Where | Provenance |
|---|---|---|
| 188-row US Foods vs Shamrock comparison | `backend/app/seed/data/us_foods_vs_shamrock.json` | Susan's workbook (`docs/source/US_Foods_vs_Shamrock_Price_Comparison.pdf`), cross-validated line-by-line against the live US Foods order guide — 100% product#/price match |
| US Foods Order Guide 2026 (188 products, printed 6/22/2026) | `docs/source/US_Foods_Order_Guide_2026.pdf` | Live export for SNAKES & LATTES TEMPE LLC |
| Shoreline catalog (129 items) | `backend/app/seed/data/shoreline_catalog.json` + `docs/source/Order_Guide_Shoreline.pdf` | Shoreline Supply Co. order guide printed 7/8/2026 |
| Supply Agent backend + page | `backend/app/routers/supply.py`, `backend/app/seed/supply_agent.py`, `frontend/src/pages/SupplyAgent.tsx` | Built and verified on real data |
| Engagement plan structure (phases, data checklist, milestones) | `backend/app/seed/snakes_and_lattes.py` `ENGAGEMENT_PLAN` | Real July 2026 proposal |
| Location names/addresses (Tempe / Chicago / Tucson) | same file, `LOCATIONS` | Real venues |

### REAL data — exists but not yet in the repo (Phase 2 input)
Two real invoices live in the customer's shared Google Drive folder
("Tempe Food Purchase Comparision" → "US Foods Invoices"):
- **US Foods invoice #5022857, dated 06/04/2026** (5 photographed pages — note: dated ~3 weeks
  before the 6/22/2026 order guide print, so guide-vs-invoice drift is measurable)
- **Shoreline Supply Co. invoice #2027803, dated 04/03/2026**

They are photo scans; they arrive as structured CSV (schema in §4.1) or as image/PDF uploads.
Build the pipeline so either path works. Do not fabricate invoice lines while waiting.

### FAKE data — purge completely (Phase 0)
All of it lives in `backend/app/seed/snakes_and_lattes.py` and flows into Mongo at seed time:
- `ITEM_CATALOG` — 18 invented menu items with invented prices/food costs/base units
- PMIX records (baseline + post period) — fabricated unit sales scaled to revenue targets
- `financials` — fabricated (`food_cost = 31% of revenue`, etc.)
- `labor_matrix` — invented hours and rates
- `reconciliation_runs` — derived from the fake PMIX/financials
- `recommendations` — generated from fake items
- Post-period "validation" actuals incl. `IMPLEMENTED_PRICE_BUMPS` and `ELASTICITY_DIP`
- `COMPETITORS_BY_LOCATION` prices — real venues, unverified prices → remove prices, keep venue
  names/addresses only as the proposal's *draft competitor list* (clearly labeled unconfirmed)
- `target_q2_fnb_revenue` / `annualized_fnb_revenue_estimate` — invented; remove
- `backend/app/seed/rook_and_roast.py` — legacy fictional tenant: delete the file, delete the
  `rook-roast` mention in `backend/.env.example`, delete `LEGACY_DEMO_TOKENS` handling in
  `frontend/src/lib/api.ts`

---

## 2. Phase 0 — Purge synthetic data everywhere

1. Delete `backend/app/seed/rook_and_roast.py`.
2. Rewrite `backend/app/seed/snakes_and_lattes.py` to seed ONLY:
   - the tenant (keep slug `snakes-and-lattes-us` and token `snakes-lattes-demo-token` so the
     deployed frontend keeps working),
   - the three locations with real names/addresses/concept notes — **no** revenue estimates,
     no seasons math, no labor, no sqft-derived anything (sqft itself is fine if from proposal),
   - the engagement plan (real proposal content — keep as is, including TBA fees),
   - the draft competitor venue list without prices (rename collection field or add
     `price: null`, `status: "draft — confirm at kickoff"`).
3. Remove all seeding of: `menu_items`, `pmix_records`, `labor_matrix`, `financials`,
   `reconciliation_runs`, `competitors` prices, `recommendations`, and any validation baselines.
4. Migration/cleanup: on startup (or a one-off admin script `backend/app/seed/purge_synthetic.py`),
   delete existing documents in those collections for this tenant so the **deployed** Render
   database is cleaned too, not just fresh installs. Make it idempotent and logged.
5. Update `backend/tests/` — tests asserting fake-data behavior (`test_snakes_and_lattes_seed.py`,
   smoke tests that expect items/recommendations) must be rewritten against the new reality:
   seed produces tenant + locations + engagement plan + supply data + zero menu analytics.
6. Frontend pages that consumed fake data get honest empty states (§5). Nothing 404s, nothing
   shows `NaN`, nothing renders an empty chart as if it were data.

**Acceptance:** a fresh seed + full click-through of every page shows only: real supply data,
real engagement plan, real locations, and empty states. `pytest` green. No reference to
Rook & Roast anywhere (`grep -ri rook` returns nothing).

---

## 3. Phase 1 — Supply Agent becomes the flagship page

- Make `/supply-agent` the default landing route (redirect `/` → `/supply-agent` until PMIX data
  exists; keep nav order: Supply Agent first).
- Keep everything already built (KPIs, trusted-comparison table, biggest movers, Shoreline
  reference catalog, price-drift stub). It has been verified against source; do not regress it.
- Re-verify after refactors: `GET /api/supply/summary` totals must match an independent recompute
  from `us_foods_vs_shamrock.json` (write this as a pytest, not a manual check).

---

## 4. Phase 2 — Invoice ingestion (unlocks actual-spend truth)

### 4.1 CSV import schema (primary path — Susan's invoices are being transcribed externally)
Endpoint: `POST /api/supply/invoices/import` (CSV multipart or JSON array). One row per line item:

```
supplier,invoice_number,invoice_date,product_number,description,brand,pack_size,qty_shipped,unit,unit_price,extended_price,line_type
US Foods,5022857,2026-06-04,8002164,"SAUCE, SOY PLASTIC JUG",KIKKOMAN,4/1 GA,2,CS,58.29,116.58,product
US Foods,5022857,2026-06-04,,,,"",1,EA,12.50,12.50,fuel_surcharge
```

- `line_type` ∈ `product | fuel_surcharge | delivery_fee | split_case_fee | tax | credit | other_fee`
- Collections: `supplier_invoices` (header: supplier, number, date, subtotal, fees_total,
  invoice_total, source `csv|upload`, tenant_id) and `supplier_invoice_lines`.

### 4.2 The validation gate (this is the accuracy moat — do not skip)
On import, before anything is queryable:
- per line: `qty_shipped x unit_price == extended_price` (±$0.01)
- per invoice: `sum(product lines) + sum(fee lines) == invoice_total` (±$0.05)
- product_number must exist in the order-guide data → else flag `unknown_sku` (could be a
  substitution — that is a *finding*, not an error)
- failures land in `data_quality_flags` with row context and are shown in a review UI panel;
  the import still completes with flagged rows quarantined out of aggregates.

### 4.3 File-upload path (photographed invoices)
`POST /api/supply/invoices/upload` accepts PDF/JPG/PNG, stores to GridFS or disk, status
`needs_transcription`. If `ANTHROPIC_API_KEY` is set (already in `.env.example`), run vision
extraction (model: `claude-sonnet-5`, one page per request, temperature 0, prompt returns the
§4.1 schema as JSON) and route the result through the same §4.2 gate with
`match_confidence: "OCR"` — OCR-sourced lines are excluded from headline KPIs until a human
marks them reviewed in the UI. If no key, the file just waits in `needs_transcription`; the CSV
path is never blocked by this.

---

## 5. Phase 3 — Truth surfaces ("show her money she hasn't seen")

Each card below states the data source and the computation. The lead has hand-verified the
cited example numbers against the source PDFs — **recompute them from data; never hardcode.**
Ship each surface only when its numbers reproduce from raw data in a pytest.

### 5.1 Guide-vs-invoice price drift (activates when invoice #5022857 lands)
Join `supplier_invoice_lines` to order-guide prices on `product_number`. Surface per SKU:
guide price, invoice price, Δ$, Δ%, direction. Headline: total overcharge vs guide across the
invoice. The existing dashed "Price Drift Detection" stub on the Supply Agent page becomes live.
Note the timing asymmetry honestly in the UI: invoice 06/04 predates guide print 06/22, so label
it "guide vs most recent invoice" not "overcharge" unless invoice > guide.

### 5.2 Fee & surcharge ledger
Sum all non-product `line_type`s per invoice and cumulatively. Show: fees as % of product spend,
projected annualized fee cost (only once ≥2 invoices exist — until then show per-invoice actuals
only, no annualization). Fuel surcharges, delivery fees, split-case fees are exactly the invisible
spend Susan asked us to expose.

### 5.3 Split-case premium report (buildable TODAY from the order guide)
The US Foods guide lists both case and each prices for a subset of items. Extract both prices
(column-aware, §0.6), compute `each_premium_pct = (EA_price − CS_price/units_per_case) / (CS_price/units_per_case)`.
Lead-verified examples from the guide text: Kikkoman soy sauce 4/1 GA $58.29/CS vs $18.94/EA → +30.0%;
Lea & Perrins Worcestershire 3/1 GA $86.81/CS vs $37.62/EA → +30.0%; Monarch mayonnaise 4/1 GA
$49.95/CS vs $16.23/EA → +30.0%; Sweet Baby Ray's BBQ 4/1 GA $64.15/CS vs $20.85/EA → +30.0%.
The premium appears to be a consistent ~30% policy — verify across ALL dual-priced lines and
report the distribution. UI copy: "every split-case (each) purchase pays ~30% over the case rate;
here is what that costs at your volumes once invoices show how often you buy eaches."

### 5.4 Same-vendor duplicate-item spread (Shoreline, buildable TODAY)
Shoreline's own guide lists near-identical items at different prices. Lead-verified:
- 9" jumbo toilet paper, Case/12EA: item 10017500 at **$32.31** vs item 10120500 ("Right Choice")
  at **$48.94** — 51.5% spread on the same spec. If the store orders the wrong code, that's
  ~$16.63 lost per case.
- 32oz barista oat milk per bottle: Califia 6-pack $17.88 → $2.98/btl; Pacific 12-pack $38.50 →
  $3.21/btl; Califia 12-pack $39.15 → $3.26/btl; Ghost Town 6-pack $21.85 → $3.64/btl.
  Two Califia 6-packs ($35.76) beat one Califia 12-pack ($39.15) — a **negative volume discount**
  of $3.39 per 12 bottles on the same product family.
Build: normalize Shoreline items to $/unit within category clusters (cluster by normalized
product name + packaging), flag clusters whose min/max spread > 10%, render a "Duplicate & Spread"
panel with the cheapest-code recommendation per cluster. Confidence-tier the clustering; only
High-confidence clusters count toward the headline savings number.

### 5.5 Unpriced items (buildable TODAY)
8 of 188 US Foods guide lines carry **"No Price"** (e.g., line 43 `1015193` yellow jumbo onions
50 LB, line 98 strawberries, lines 140/141 mozzarella). Every unpriced guide item is uncontrolled
spend — the charged price appears only on the invoice, with no reference to check it against.
Surface the list with copy: "these arrive at whatever price is on the truck — ask US Foods to
publish guide prices, or we benchmark them from your invoices."

### 5.6 Cross-supplier switching savings (already live — keep)
The existing trusted-lines switching-savings KPI stays. Add per-category grouping (produce,
proteins, dry goods…) derived from the guide's section headers so Susan sees WHERE Shamrock wins.

### 5.7 Needs-review queue as a feature
The ~15 weak/likely-wrong matches are currently just filtered out. Give them a review UI:
side-by-side item cards with an operator action (confirm match / reject / fix). Every resolved
row moves into the trusted pool and updates the KPIs live. This turns our honesty about
uncertainty into a visible workflow — exactly the accuracy story we're selling.

### 5.8 Substitution watch (activates with invoices)
Invoice lines whose product_number is absent from the order guide = probable substitutions
(`unknown_sku` flags from §4.2). Surface them: "you were shipped items that aren't on your guide —
same price? bigger pack? Check these."

---

## 6. Phase 4 — Honest empty states for the menu-engineering pages

For `BrandDashboard`, `LocationDashboard`, `ItemAnalysisTable`, `ApprovalQueue`, `Validation`:
- When the underlying collections are empty, render a purpose-built empty state (not a spinner,
  not zeros): what the page will show, which data unlocks it, and its due date pulled live from
  the engagement plan's `calendar.data_checklist` (e.g., "Awaiting 90-day Toast PMIX export —
  due 2026-07-13"). One shared `<AwaitingData>` component; each page passes its checklist keys.
- The pipeline (`build_location_item_metrics`, quadrant classification, recommendations,
  validation engine) is real code — keep it all; it activates when real PMIX/financials arrive.
- EngagementPlan page: keep as is (real proposal content).

---

## 7. Definition of Done (per phase, enforced at review)

1. `pytest` green, including NEW tests: seed contents, import validation gate (happy + each
   failure class), each truth surface's numbers recomputed from raw seed JSON inside the test.
2. An independent recompute script `backend/scripts/verify_numbers.py` that reads ONLY
   `docs/source/` PDFs + seed JSONs and re-derives every headline number the UI shows, printing
   a pass/fail table. Run it in CI or at least paste its output in the PR.
3. Playwright screenshots of every page (desktop + one mobile width) attached to the PR.
4. No console errors, no `NaN`/`undefined` rendered, no dead nav links.
5. PR description lists every user-visible number with its source trace (file + line/row).
6. Branch: work on feature branches, PR back to `main` as **draft** for approval. Never merge
   without lead + founder sign-off.

## 8. Explicitly out of scope (do not build yet)
- Menu-engineering analytics on synthetic data (purged; waits for real Toast PMIX).
- Multi-tenant onboarding flows, billing, auth changes.
- Annualized projections from a single invoice (forbidden by §5.2 until ≥2 invoices).
- Any Shoreline vs US Foods/Shamrock price comparison (different product mix — already scoped out
  by the customer's own workbook; keep Shoreline as reference catalog + §5.4 internal spread).
