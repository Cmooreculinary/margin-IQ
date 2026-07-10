# Margin IQ — Real-Data Implementation Spec
**Status:** Phase 0 – Purge & Foundation  
**Customer:** Snakes & Lattes Tempe LLC (US Foods #54158019, Phoenix div. 4146)  
**Lead:** Claude (Margin IQ session)  
**Implementer:** Codex  
**Return Protocol:** All phases as PRs to `main` for lead + founder approval before merge.

---

## The Accuracy Contract (Binding)

This customer explicitly tests us for **accuracy in all areas**. These are not suggestions.

| Rule | Intent | Violation = Fail |
|---|---|---|
| **No invented numbers** | Every figure traced to source doc, seed file, or arithmetic | Hardcoded number in UI without source |
| **No synthetic placeholders** | Real data only; empty states name missing input | Sample data shown instead of honest gaps |
| **Compute, don't transcribe** | Derived figures (%, savings, premiums) computed at request time | Figures hardcoded in copy or JSX |
| **Verify extraction 2× independently** | PDF extractions validated by re-parse + row-math checks | Silent correction of mismatches |
| **Label confidence tiers** | Fuzzy matches, OCR, weak data visible in UI | Weak data aggregated into headline KPIs |
| **PDF layout parsing (US Foods specific)** | Text layer wraps/interleaves rows; use column-aware extraction (pdfplumber `extract_table`) | Row-regex parsing causes mispairs across 188-line guide |

---

## Part 1: Current State Audit

### Real Data (Keep & Build On)

| Data | Location | Source | Provenance |
|---|---|---|---|
| **US Foods vs Shamrock comparison (188 rows)** | `backend/app/seed/data/us_foods_vs_shamrock.json` | Susan's workbook | PDF-validated line-by-line: 100% product#/price match |
| **US Foods Order Guide 2026 (188 products)** | `docs/source/US_Foods_Order_Guide_2026.pdf` | Live export | Printed 6/22/2026 for Snakes & Lattes Tempe |
| **Shoreline catalog (129 items)** | `backend/app/seed/data/shoreline_catalog.json` + `docs/source/Order_Guide_Shoreline.pdf` | Shoreline Supply Co. | Printed 7/8/2026 |
| **Supply Agent (backend + UI)** | `backend/app/routers/supply.py`, `frontend/src/pages/SupplyAgent.tsx` | Real data | Built & verified on real data |
| **Engagement plan (phases, checklist, milestones)** | `backend/app/seed/snakes_and_lattes.py` `ENGAGEMENT_PLAN` | July 2026 proposal | Real customer document |
| **Location names/addresses (Tempe/Chicago/Tucson)** | `backend/app/seed/snakes_and_lattes.py` `LOCATIONS` | Real venues | Verified addresses |

### Real Data Waiting (Phase 2 Input — Do Not Fabricate)

Two real invoices in customer's Google Drive ("Tempe Food Purchase Comparison" → "US Foods Invoices"):
- **US Foods invoice #5022857, dated 06/04/2026** (5 photographed pages)  
  *Note:* Dated ~3 weeks before 6/22/2026 guide print → guide-vs-invoice drift is measurable
- **Shoreline Supply Co. invoice #2027803, dated 04/03/2026**

**Critical:** Do not invent invoice data while waiting. Build the pipeline; gate all imports through validation (§4.2). CSV or image paths both work.

### Synthetic Data (Purge Completely — Phase 0)

| What | Where | Action |
|---|---|---|
| `ITEM_CATALOG` (18 invented menu items) | `backend/app/seed/snakes_and_lattes.py` | Delete |
| PMIX records (fabricated unit sales) | seed file | Delete |
| Financials (fake food_cost=31%, etc.) | seed file | Delete |
| Labor matrix (invented hours/rates) | seed file | Delete |
| Reconciliation runs | seed file | Delete |
| Recommendations | seed file | Delete |
| Validation actuals + `IMPLEMENTED_PRICE_BUMPS` | seed file | Delete |
| Competitor prices (unverified) | seed file | Delete; keep venue names/addresses as "draft — confirm at kickoff" |
| Revenue targets + annualized estimates | seed file | Delete |
| Rook & Roast tenant (legacy fiction) | `backend/app/seed/rook_and_roast.py` | **Delete entire file** |
| Rook & Roast references | `backend/.env.example`, `frontend/src/lib/api.ts` | Delete all mentions |

---

## Part 2: Phase 0 – Purge & Foundation (Acceptance Criteria)

### Phase 0.1: Delete Legacy

- [ ] Delete `backend/app/seed/rook_and_roast.py`
- [ ] Remove all Rook & Roast from `.env.example` and `frontend/src/lib/api.ts`
- [ ] `grep -ri rook` returns nothing

### Phase 0.2: Rewrite Seed to Real Data Only

Rewrite `backend/app/seed/snakes_and_lattes.py` to seed **only**:

```python
# Seeds:
- tenant (slug: "snakes-and-lattes-us", token: "snakes-lattes-demo-token")
- locations (3: Tempe, Chicago, Tucson with real names/addresses/concept notes)
- engagement_plan (real July 2026 proposal content)
- draft_competitors (venue names/addresses, NO prices, status: "draft — confirm at kickoff")
- supply_data (US Foods guide + Shoreline catalog from JSON files)

# Does NOT seed:
- menu_items
- pmix_records
- labor_matrix
- financials
- reconciliation_runs
- item_metrics
- recommendations
- validation_baselines
```

### Phase 0.3: Cleanup Existing Data (Deployed Render DB)

Create `backend/app/seed/purge_synthetic.py`:

```python
async def purge_synthetic_data(db, tenant_id):
    """Idempotent cleanup: delete fake collections for a tenant on startup."""
    fake_collections = [
        "menu_items", "pmix_records", "labor_matrix", "financials",
        "reconciliation_runs", "item_metrics", "recommendations",
        "baselines", "validation_runs"
    ]
    for collection_name in fake_collections:
        deleted = await db[collection_name].delete_many({"tenant_id": tenant_id})
        logger.info(f"Purged {deleted.deleted_count} docs from {collection_name}")
```

Run in lifespan hook on deployed instance so Render DB is cleaned, not just fresh installs.

### Phase 0.4: Rewrite Tests

- [ ] Rewrite tests that assert fake-data behavior
- [ ] Delete `test_snakes_and_lattes_seed.py` (was testing fake items/recommendations)
- [ ] New tests verify: seed produces tenant + locations + engagement plan, zero menu analytics
- [ ] `pytest` green

### Phase 0.5: Frontend Empty States

All pages that consumed fake data now show honest empty states (design in §6):

| Page | Empty State Message |
|---|---|
| `/items` | "Awaiting 90-day Toast PMIX export — due 2026-07-13" |
| `/recommendations` | "Awaiting 90-day Toast PMIX export — due 2026-07-13" |
| `/validation` | "Awaiting baseline lock & post-period data — due 2026-09-15" |
| `/dashboard/brand`, `/dashboard/location/:id` | Same as `/items` |

Use shared `<AwaitingData>` component; pass checklist keys from `engagement_plan.calendar.data_checklist`.

**Acceptance:** Fresh seed + full click-through shows: real supply data, real engagement plan, real locations, empty states. No NaN, no zeros-as-data, no sample content. `pytest` green.

---

## Part 3: Phase 1 – Supply Agent (Flagship Page)

### Phase 1.1: Navigation & Routing

- [ ] Make `/supply-agent` the default landing (redirect `/` → `/supply-agent` until PMIX data exists)
- [ ] Update nav order: Supply Agent first
- [ ] Keep all existing KPIs, trusted-comparison table, biggest movers, Shoreline catalog, price-drift stub

### Phase 1.2: Verification

Add pytest:

```python
def test_supply_summary_totals():
    """Recompute GET /api/supply/summary from us_foods_vs_shamrock.json independently."""
    # Load raw JSON
    with open("backend/app/seed/data/us_foods_vs_shamrock.json") as f:
        data = json.load(f)
    
    # Hand-compute totals
    expected_guide_total = sum(row.get("us_foods_price", 0) * row.get("qty", 1) for row in data)
    expected_shamrock_total = sum(row.get("shamrock_price", 0) * row.get("qty", 1) for row in data)
    
    # Hit API
    response = client.get("/api/supply/summary", headers=auth_header)
    assert response.json()["us_foods_total"] == expected_guide_total
    assert response.json()["shamrock_total"] == expected_shamrock_total
```

**Acceptance:** GET `/api/supply/summary` totals match independent recompute from seed JSON. Pytest validates on every run.

---

## Part 4: Phase 2 – Invoice Ingestion & Validation Gate

### Phase 2.1: CSV Import Schema

Endpoint: `POST /api/supply/invoices/import`

**Input format (multipart or JSON array):**

```csv
supplier,invoice_number,invoice_date,product_number,description,brand,pack_size,qty_shipped,unit,unit_price,extended_price,line_type
US Foods,5022857,2026-06-04,8002164,SAUCE SOY PLASTIC JUG,KIKKOMAN,4/1 GA,2,CS,58.29,116.58,product
US Foods,5022857,2026-06-04,,,,,1,EA,12.50,12.50,fuel_surcharge
US Foods,5022857,2026-06-04,,,,,1,EA,15.00,15.00,delivery_fee
```

**Schema:**
- `line_type` ∈ {`product`, `fuel_surcharge`, `delivery_fee`, `split_case_fee`, `tax`, `credit`, `other_fee`}
- Collections:
  - `supplier_invoices`: header metadata (supplier, number, date, subtotal, fees_total, invoice_total, source: csv|upload, tenant_id, created_at)
  - `supplier_invoice_lines`: detail rows (all columns above + line_id reference)

### Phase 2.2: Validation Gate (Accuracy Moat)

**Before any data is queryable, validate:**

| Check | Tolerance | Action |
|---|---|---|
| `qty_shipped × unit_price == extended_price` (per line) | ±$0.01 | Flag if fails |
| `sum(product lines) + sum(fee lines) == invoice_total` (per invoice) | ±$0.05 | Flag if fails |
| `product_number` exists in order-guide data | N/A | Flag as `unknown_sku` if absent |

**Failures → `data_quality_flags` collection:**

```python
@dataclass
class DataQualityFlag:
    flag_type: str  # "line_math_fail", "total_mismatch", "unknown_sku", "duplicate_invoice"
    severity: str   # "error", "warning", "info"
    invoice_id: str
    line_index: int | None
    message: str
    context: dict   # row data for user review
    created_at: datetime
```

Flagged rows are **quarantined out of aggregates** (supply KPIs) until resolved. Import completes; user sees review UI (§2.4).

**Test (adversarial data):**

```python
def test_validation_gate_line_math_fail():
    """qty × price ≠ extended; should flag, not error."""
    payload = [{
        "supplier": "US Foods", "invoice_number": "TEST001", "invoice_date": "2026-06-04",
        "product_number": "8002164", "qty_shipped": 2, "unit": "CS",
        "unit_price": 58.29, "extended_price": 116.57,  # Off by $0.01
        "line_type": "product"
    }]
    response = client.post("/api/supply/invoices/import", json=payload, headers=auth_header)
    assert response.status_code == 201  # Import succeeds
    flags = response.json()["quality_flags"]
    assert any(f["flag_type"] == "line_math_fail" for f in flags)
    
def test_validation_gate_unknown_sku():
    """product_number not in guide → flag, not error."""
    payload = [{
        "supplier": "US Foods", "invoice_number": "TEST001", "invoice_date": "2026-06-04",
        "product_number": "9999999", "qty_shipped": 1, "unit": "CS",
        "unit_price": 50.00, "extended_price": 50.00, "line_type": "product"
    }]
    response = client.post("/api/supply/invoices/import", json=payload, headers=auth_header)
    assert response.status_code == 201
    flags = response.json()["quality_flags"]
    assert any(f["flag_type"] == "unknown_sku" for f in flags)
```

### Phase 2.3: File-Upload Path (Photographed Invoices)

Endpoint: `POST /api/supply/invoices/upload`

- Accepts: PDF, JPG, PNG (store to GridFS or disk)
- Sets status: `needs_transcription`
- If `ANTHROPIC_API_KEY` set:
  - Extract vision (Claude Sonnet, temperature=0, one page per request)
  - Route result through §2.2 validation gate
  - Mark OCR lines with `match_confidence: "OCR"` — **excluded from headline KPIs until human review**
- If no key: file waits in `needs_transcription`; CSV path never blocked

### Phase 2.4: Review UI & Operator Action

New page: `/invoices` (in TopNav after Supply Agent)

**Layout:**
- Upload zone (drag CSV or image)
- Recent imports list (invoice_number, date, line count, flag count)
- Review panel (per invoice):
  - Flagged rows highlighted in table
  - Action per row: "Confirm" / "Reject" / "Fix & re-enter"
  - Resolved rows move to "approved" status, re-enter aggregates

**Wireframe notes:**
- Flagged rows: yellow highlight, icon + severity
- Line-math fails: show computed vs. entered, allow override with confirmation checkbox
- Unknown SKUs: show product_number + description, allow "substitute for [trusted SKU]" dropdown
- Once all flags resolved: line moves to `approved` status, supply KPIs update live

---

## Part 5: Phase 3 – Truth Surfaces

### Prerequisite: Lead-Verified Numbers

All numbers cited below have been hand-verified by lead against source PDFs. **Do not hardcode.** Recompute from raw seed JSON / invoices inside pytests before shipping.

### Phase 3.1: Guide-vs-Invoice Price Drift

**Activates when:** Invoice #5022857 (06/04/2026) is imported.

**Computation:**

```python
def price_drift_analysis(invoice_id: str, db) -> dict:
    """Join invoice lines to order-guide prices on product_number."""
    invoice = await db.supplier_invoices.find_one({"_id": invoice_id})
    lines = await db.supplier_invoice_lines.find({"invoice_id": invoice_id}).to_list(length=None)
    
    results = []
    total_overage = 0.0
    for line in lines:
        if line["line_type"] != "product":
            continue
        guide_row = us_foods_guide.get(line["product_number"])
        if not guide_row:
            continue
        guide_price = guide_row["price"]
        invoice_price = line["unit_price"]
        delta_pct = (invoice_price - guide_price) / guide_price if guide_price else 0
        total_extended_delta = (invoice_price - guide_price) * line["qty_shipped"]
        total_overage += total_extended_delta
        results.append({
            "plu": line["product_number"],
            "description": line["description"],
            "guide_price": guide_price,
            "invoice_price": invoice_price,
            "delta_dollars": total_extended_delta,
            "delta_pct": delta_pct,
            "direction": "+" if delta_pct > 0 else "−"
        })
    
    return {
        "invoice_number": invoice["number"],
        "invoice_date": invoice["date"],
        "guide_print_date": "2026-06-22",
        "note": "Invoice predates guide print by 18 days; label as 'guide vs. most recent invoice' not 'overcharge'",
        "lines": sorted(results, key=lambda x: x["delta_dollars"], reverse=True),
        "total_overage": total_overage
    }
```

**UI (update dashed stub on Supply Agent page):**
- Headline: "Invoice #5022857 vs. 6/22 guide: **+$X overage** across N items"
- Table: product, guide price, invoice price, Δ$, Δ%, direction
- Note timestamp asymmetry: "06/04 invoice vs. 06/22 guide print"

**Test:**

```python
def test_price_drift_recompute_from_invoice():
    """Hand-verify 3 lead-cited examples from invoice #5022857."""
    # (Lead will provide specific rows: "Kikkoman soy $X vs guide $Y", etc.)
    response = client.get("/api/supply/price-drift/invoice/5022857", headers=auth_header)
    data = response.json()
    # Assert specific product rows match lead's manual audit
```

### Phase 3.2: Fee & Surcharge Ledger

**Computation:**

```python
def fee_ledger(tenant_id: str, db) -> dict:
    """Sum all non-product line_types per invoice + cumulative."""
    invoices = await db.supplier_invoices.find({"tenant_id": tenant_id}).to_list(length=None)
    
    by_invoice = []
    cumulative_by_type = {}
    
    for invoice in invoices:
        lines = await db.supplier_invoice_lines.find({"invoice_id": invoice["_id"]}).to_list(length=None)
        invoice_totals = {}
        for line in lines:
            if line["line_type"] == "product":
                continue
            lt = line["line_type"]
            invoice_totals[lt] = invoice_totals.get(lt, 0.0) + line["extended_price"]
            cumulative_by_type[lt] = cumulative_by_type.get(lt, 0.0) + line["extended_price"]
        
        product_subtotal = sum(l["extended_price"] for l in lines if l["line_type"] == "product")
        fees_total = sum(invoice_totals.values())
        fee_pct = (fees_total / product_subtotal * 100) if product_subtotal else 0
        
        by_invoice.append({
            "invoice_number": invoice["number"],
            "invoice_date": invoice["date"],
            "product_subtotal": product_subtotal,
            "fees_by_type": invoice_totals,
            "fees_total": fees_total,
            "fees_as_pct_of_products": fee_pct
        })
    
    # Annualization (only if ≥2 invoices)
    annualized = {}
    if len(by_invoice) >= 2:
        # Simple: (cumulative / days_spanned) × 365
        earliest = min(by_invoice, key=lambda x: x["invoice_date"])["invoice_date"]
        latest = max(by_invoice, key=lambda x: x["invoice_date"])["invoice_date"]
        days = (latest - earliest).days
        if days > 0:
            annualized = {
                lt: (total / days * 365)
                for lt, total in cumulative_by_type.items()
            }
    
    return {
        "by_invoice": by_invoice,
        "cumulative_by_type": cumulative_by_type,
        "annualized_by_type": annualized,
        "note": "Annualization only shown with ≥2 invoices; until then, per-invoice actuals only"
    }
```

**UI (new card on Supply Agent page):**
- Headline: "Fees & surcharges: **$X fuel + $Y delivery + $Z split-case = $Total** (Z% of product spend)"
- Table: fee type, invoice 1, invoice 2, … cumulative, annualized (if ≥2)
- Copy: "These are the invisible spend drivers — fuel surcharges, delivery fees, split-case premiums. Here's what they cost."

**Test:**

```python
def test_fee_ledger_per_invoice():
    """Single invoice: fees by type, % of products."""
    response = client.get("/api/supply/fees/ledger", headers=auth_header)
    data = response.json()["by_invoice"][0]
    assert data["fees_as_pct_of_products"] >= 0
    # Assert specific fee types present

def test_fee_ledger_no_annualization_with_one_invoice():
    """With only 1 invoice, annualized_by_type is empty."""
    response = client.get("/api/supply/fees/ledger", headers=auth_header)
    data = response.json()
    assert data["annualized_by_type"] == {}
    assert "note" in data and "≥2 invoices" in data["note"]
```

### Phase 3.3: Split-Case Premium Report (Buildable Today)

**US Foods guide**: lists both CS (case) and EA (each) prices for select items.

**Lead-verified examples:**
- Kikkoman soy sauce 4/1 GA: $58.29/CS vs $18.94/EA → premium: +30.0%
- Lea & Perrins Worcestershire 3/1 GA: $86.81/CS vs $37.62/EA → premium: +30.0%
- Monarch mayonnaise 4/1 GA: $49.95/CS vs $16.23/EA → premium: +30.0%
- Sweet Baby Ray's BBQ 4/1 GA: $64.15/CS vs $20.85/EA → premium: +30.0%

**Computation (column-aware PDF extraction first):**

```python
def extract_dual_prices_from_guide(pdf_path: str) -> list[dict]:
    """Use pdfplumber column-aware extraction, not line regex."""
    import pdfplumber
    results = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            table = page.extract_table(
                table_settings={"vertical_strategy": "lines", "horizontal_strategy": "lines"}
            )
            if not table:
                continue
            for row in table:
                # Columns: (PLU, Desc, Pack_Size, CS_Price, EA_Price, ...)
                # Only capture rows where both CS_Price and EA_Price are populated
                if row[3] and row[4]:  # Both prices
                    cs_price = float(row[3])
                    ea_price = float(row[4])
                    units_per_case = int(row[2].split("/")[0])  # "4/1 GA" → 4
                    ea_from_cs = cs_price / units_per_case
                    premium = (ea_price - ea_from_cs) / ea_from_cs
                    results.append({
                        "plu": row[0],
                        "description": row[1],
                        "pack_size": row[2],
                        "cs_price": cs_price,
                        "ea_price": ea_price,
                        "ea_from_cs_basis": ea_from_cs,
                        "premium_pct": premium,
                        "units_per_case": units_per_case
                    })
    return results

def split_case_premium_analysis(db) -> dict:
    """Analyze all dual-priced items from guide."""
    dual_priced = extract_dual_prices_from_guide("docs/source/US_Foods_Order_Guide_2026.pdf")
    
    premiums = [item["premium_pct"] for item in dual_priced]
    return {
        "count": len(dual_priced),
        "items": sorted(dual_priced, key=lambda x: x["premium_pct"], reverse=True),
        "avg_premium_pct": statistics.mean(premiums),
        "median_premium_pct": statistics.median(premiums),
        "min_premium_pct": min(premiums),
        "max_premium_pct": max(premiums),
        "distribution": {
            "under_10pct": len([x for x in premiums if x < 0.10]),
            "10_20pct": len([x for x in premiums if 0.10 <= x < 0.20]),
            "20_30pct": len([x for x in premiums if 0.20 <= x < 0.30]),
            "over_30pct": len([x for x in premiums if x >= 0.30]),
        }
    }
```

**UI (new panel on Supply Agent):**
- Headline: "Split-case premium: avg **Z%** (range X%–Y%) across N items"
- Distribution: "80 items at ~30% premium, 8 items at 15%"
- Table: product, pack, CS price, EA price, EA basis, premium%
- Copy: "Every each (EA) purchase pays a premium over the case rate. At your volumes [once invoices show frequency], this costs $X annually."

**Test:**

```python
def test_split_case_premium_extraction():
    """Recompute lead-verified examples from guide PDF."""
    data = split_case_premium_analysis(None)
    # Find Kikkoman soy in results
    kikkoman = [x for x in data["items"] if "KIKKOMAN" in x["description"].upper()][0]
    assert abs(kikkoman["premium_pct"] - 0.30) < 0.01  # ±1%
    # Repeat for Lea & Perrins, Monarch, etc.

def test_split_case_premium_distribution():
    """Verify distribution buckets sum to total count."""
    data = split_case_premium_analysis(None)
    total = sum(data["distribution"].values())
    assert total == data["count"]
```

### Phase 3.4: Same-Vendor Duplicate-Item Spread (Shoreline, Buildable Today)

**Lead-verified examples from Shoreline guide:**
- 9" jumbo toilet paper: item 10017500 at $32.31 vs item 10120500 ("Right Choice") at $48.94 → **51.5% spread**  
  *Savings if correct SKU ordered:* $16.63/case
- 32oz barista oat milk per bottle:
  - Califia 6-pack: $17.88 → $2.98/btl
  - Pacific 12-pack: $38.50 → $3.21/btl
  - Califia 12-pack: $39.15 → $3.26/btl
  - Ghost Town 6-pack: $21.85 → $3.64/btl
  - *Negative volume discount:* Two Califia 6-packs ($35.76) beat one Califia 12-pack ($39.15) by **$3.39 per 12 bottles**

**Computation:**

```python
def cluster_similar_items(items: list[dict]) -> dict[str, list[dict]]:
    """Normalize product names to category + brand + packaging."""
    from difflib import SequenceMatcher
    
    clusters = {}
    for item in items:
        # Extract brand + key keywords (e.g., "oat milk", "toilet paper")
        normalized = normalize_product_name(item["description"])
        # Fuzzy-match to existing cluster key or create new
        matched_key = None
        for key in clusters.keys():
            if SequenceMatcher(None, normalized, key).ratio() > 0.75:
                matched_key = key
                break
        if not matched_key:
            matched_key = normalized
        clusters.setdefault(matched_key, []).append(item)
    return clusters

def duplicate_spread_analysis(db) -> dict:
    """Find clusters where min/max spread > 10% within same category."""
    shoreline_items = load_shoreline_catalog()
    clusters = cluster_similar_items(shoreline_items)
    
    findings = []
    for cluster_key, items in clusters.items():
        if len(items) < 2:
            continue
        
        # Normalize to $/unit
        unit_prices = []
        for item in items:
            # Extract size, compute $/unit
            unit_price = item["price"] / item["quantity"]
            unit_prices.append((item, unit_price))
        
        unit_prices.sort(key=lambda x: x[1])
        min_item, min_price = unit_prices[0]
        max_item, max_price = unit_prices[-1]
        spread_pct = (max_price - min_price) / min_price
        
        if spread_pct > 0.10:
            findings.append({
                "cluster": cluster_key,
                "spread_pct": spread_pct,
                "item_count": len(items),
                "min_item": min_item,
                "min_price_per_unit": min_price,
                "max_item": max_item,
                "max_price_per_unit": max_price,
                "savings_per_case": (max_price - min_price) * min_item["quantity"],
                "confidence": "High" if spread_pct > 0.25 else "Review"
            })
    
    # Only High-confidence clusters → headline number
    high_conf = [f for f in findings if f["confidence"] == "High"]
    estimated_annualized_savings = sum(f["savings_per_case"] * 52 for f in high_conf)  # Rough
    
    return {
        "clusters_reviewed": len(clusters),
        "duplicates_with_spread": len(findings),
        "high_confidence_duplicates": len(high_conf),
        "estimated_annualized_savings": estimated_annualized_savings,
        "findings": sorted(findings, key=lambda x: x["spread_pct"], reverse=True)
    }
```

**UI (new panel on Supply Agent):**
- Headline: "Duplicate items (same vendor): **N clusters** with >10% spread; **$X** potential savings (high-confidence)"
- Table: item cluster, min (cheapest SKU), max (most expensive SKU), spread%, savings/case
- Row actions: "Audit usage" / "Switch to cheaper SKU"
- Copy: "These are near-identical items at wildly different prices — usually a typo, a brand switch, or a missed promotional. Check if you're ordering the expensive version."

**Test:**

```python
def test_duplicate_spread_extraction():
    """Lead-verified: 9\" toilet paper 51.5% spread, oat milk negative discount."""
    data = duplicate_spread_analysis(None)
    # Find toilet paper cluster
    tp = [f for f in data["findings"] if "toilet" in f["cluster"].lower()][0]
    assert abs(tp["spread_pct"] - 0.515) < 0.01
    # Find oat milk: should flag negative volume discount
    oat = [f for f in data["findings"] if "oat" in f["cluster"].lower()][0]
    assert oat["confidence"] == "Review"  # Unusual pattern
```

### Phase 3.5: Unpriced Items (Buildable Today from Guide)

**8 of 188 US Foods guide lines carry "No Price":**
- Line 43: PLU 1015193, yellow jumbo onions 50 LB
- Line 98: strawberries (seasonal)
- Lines 140/141: mozzarella (variants)
- (Others — lead will cite exact lines)

**Computation:**

```python
def unpriced_items_audit(pdf_path: str) -> list[dict]:
    """Extract all rows with "No Price" or blank price from guide."""
    import pdfplumber
    unpriced = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            table = page.extract_table(table_settings={...})
            for row in table:
                plu, desc, price = row[0], row[1], row[3]
                if not price or "no price" in price.lower():
                    unpriced.append({
                        "line_number": row[0],  # Guide line number
                        "plu": plu,
                        "description": desc,
                        "status": "unpriced"
                    })
    return unpriced
```

**UI (new card on Supply Agent):**
- Headline: "**8 items** arrive at whatever price is on the truck (no guide price)"
- List: line#, PLU, description
- Copy: "These are uncontrolled spend — the charged price appears only on the invoice, with no reference to check it against. Action: ask US Foods to publish guide prices for these items, or we'll benchmark them from your invoices once they arrive."

**Test:**

```python
def test_unpriced_items_count():
    """Should extract exactly 8 unpriced rows from 2026 guide."""
    data = unpriced_items_audit("docs/source/US_Foods_Order_Guide_2026.pdf")
    assert len(data) == 8
    assert any("onion" in x["description"].lower() for x in data)  # Line 43
```

### Phase 3.6: Cross-Supplier Switching Savings (Already Live — Keep)

Keep existing trusted-lines switching-savings KPI. Add **per-category grouping** derived from guide section headers:

```python
def switching_savings_by_category() -> dict:
    """Group trusted lines by section of guide (produce, proteins, dry goods, …)."""
    # (Already in seed data; just add .category to each trusted row)
    trusted = [r for r in us_foods_vs_shamrock if r["confidence"] == "High"]
    by_category = {}
    for row in trusted:
        cat = row.get("category", "Uncategorized")
        by_category.setdefault(cat, []).append(row)
    
    return {
        cat: {
            "count": len(items),
            "total_savings": sum(i["savings_dollars"] for i in items),
            "avg_savings_per_item": statistics.mean(i["savings_dollars"] for i in items)
        }
        for cat, items in by_category.items()
    }
```

**UI update:**
- Existing "Switch to Shamrock" KPI stays
- Add tabs or drill-down: "Where Shamrock wins: Produce (15 items, $X savings), Proteins (12 items, $Y), …"

### Phase 3.7: Needs-Review Queue (Largest Untapped Pool)

**Current state (lead-audited 2026-07-10):**
- High confidence: 23 rows
- Review (fuzzy match): 25 rows (+ 1 "Review – unit mismatch")
- Weak: 79 rows
- "Weak / likely wrong": 78 rows
- **165 of 188 rows idle → $X+ waiting to be claimed**

**This is the biggest single lever.** Turn honesty about uncertainty into a visible workflow.

**UI (new tab: "Needs Review" on Supply Agent or dedicated `/review` page):**

```jsx
<NeedsReviewQueue>
  {/* Side-by-side item cards */}
  {trustedItems.map(item => (
    <ItemReviewCard
      key={item.id}
      usFood={{brand, description, size, guidePrice}}
      shamrock={{brand, description, size, price}}
      currentMatch={{confidence, matchReason}}
      actions={[
        {label: "✓ Confirm match", onClick: () => confirmMatch(item.id)},
        {label: "✗ Reject", onClick: () => rejectMatch(item.id)},
        {label: "🔧 Fix SKU", onClick: () => showFixUI(item.id)}
      ]}
    />
  ))}
</NeedsReviewQueue>
```

**Per operator action:**
- "Confirm": move row to `confidence: "High"`, recalculate KPIs live
- "Reject": mark `confidence: "N/A"`, remove from totals
- "Fix SKU": show dropdown of alternate Shamrock items, suggest best match

**Workflow integration:**
- Each resolved row fires `PUT /api/supply/matches/:id/confirm` (or reject/fix)
- API updates `confidence` field in seed data / database
- KPI cards (`<SupplyAgentSummary>`) re-fetch and animate changes
- Operator sees savings change in real-time as they confirm

**Test:**

```python
def test_needs_review_queue_count():
    """Current audit: 165 non-high-confidence rows in seed data."""
    non_high = [r for r in us_foods_vs_shamrock if r["confidence"] != "High"]
    assert len(non_high) == 165

def test_confirm_match_updates_kpis():
    """Confirming a Review row promotes it to High; totals recompute."""
    # Initial KPIs
    response1 = client.get("/api/supply/summary", headers=auth_header)
    initial_total = response1.json()["total_savings"]
    
    # Confirm one Review row
    review_row = [r for r in us_foods_vs_shamrock if r["confidence"] == "Review"][0]
    client.put(f"/api/supply/matches/{review_row['id']}/confirm", headers=auth_header)
    
    # KPIs should increase
    response2 = client.get("/api/supply/summary", headers=auth_header)
    new_total = response2.json()["total_savings"]
    assert new_total > initial_total
```

### Phase 3.8: Substitution Watch (Activates with Invoices)

**Activates when:** Invoices are imported (Phase 2).

**Data:** Invoice lines whose `product_number` is absent from order guide = probable substitutions (`unknown_sku` flags from §4.2).

**UI (card on Supply Agent, or expand existing Flags panel):**
- Headline: "**3 substitutions** on invoice #5022857 — items shipped that aren't on your guide"
- Table: product#, description, supplier reason (if noted), "Same price?" ✓/✗, action
- Copy: "You were shipped items that aren't on your guide — check if they're substitutions, different sizes, or billing errors."

**Test:**

```python
def test_substitution_watch_detection():
    """Invoice with unknown SKUs → flags appear on Supply Agent."""
    # Import invoice with unknown product_number
    client.post("/api/supply/invoices/import", json=[{
        "supplier": "US Foods", "invoice_number": "5022857",
        "product_number": "9999999", "description": "MYSTERY ITEM",
        "qty_shipped": 1, "unit_price": 50.0, "extended_price": 50.0,
        "line_type": "product"
    }], headers=auth_header)
    
    # Get Supply Agent summary
    response = client.get("/api/supply/summary", headers=auth_header)
    assert "substitutions" in response.json()
    assert response.json()["unknown_sku_count"] == 1
```

---

## Part 6: Phase 4 – Honest Empty States (Menu Analytics)

For pages that consumed fake menu data, build honest empty states:

### Components Needed

**Shared component:** `frontend/src/components/AwaitingData.tsx`

```tsx
interface AwaitingDataProps {
  title: string;           // "Menu Analysis", "Recommendations", etc.
  what: string;            // What data unlocks this page
  dueDate: string;         // ISO date from engagement plan
  checklistItems: string[]; // What's needed (e.g., ["Toast PMIX", "Labor Matrix"])
}

export function AwaitingData({ title, what, dueDate, checklistItems }: AwaitingDataProps) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center">
      <Icon name="inbox-empty" className="text-4xl text-gray-300 mb-4" />
      <h2 className="text-2xl font-bold text-gray-900 mb-2">{title}</h2>
      <p className="text-lg text-gray-600 mb-6">{what}</p>
      <div className="bg-blue-50 border border-blue-200 rounded p-4 mb-6 max-w-md text-left">
        <h3 className="font-semibold text-blue-900 mb-2">Needed by {formatDate(dueDate)}:</h3>
        <ul className="list-disc list-inside text-blue-800">
          {checklistItems.map((item, i) => <li key={i}>{item}</li>)}
        </ul>
      </div>
      <a href="/engagement" className="text-blue-600 hover:underline">
        View full engagement plan →
      </a>
    </div>
  );
}
```

### Empty States by Page

| Page | Component | Message | Due Date Source |
|---|---|---|---|
| `/items` | `<AwaitingData>` | "Menu Analysis awaits 90-day Toast PMIX export (point-of-sale mix: units sold per item per daypart per location)" | `engagement_plan.calendar.data_checklist.toast_pmix_due` |
| `/recommendations` | `<AwaitingData>` | Same as `/items` | Same |
| `/dashboard/brand` | `<AwaitingData>` | Same + "Financial actuals (gross sales, COGS, labor cost by location)" | `engagement_plan.calendar.data_checklist` |
| `/dashboard/location/:id` | `<AwaitingData>` | Same | Same |
| `/approval-queue` | `<AwaitingData>` | "Awaiting menu analysis to generate recommendations" | Same |
| `/validation` | `<AwaitingData>` | "Awaiting baseline lock (90-day period close) and post-period actuals to measure realized lift" | `engagement_plan.calendar.data_checklist.validation_measure_due` |

**Test (Playwright):**

```typescript
test("items page shows honest empty state when no PMIX data", async ({ page }) => {
  await page.goto("/items");
  
  // Should see empty state, not spinner or zeros
  await expect(page.locator("text=Menu Analysis awaits")).toBeVisible();
  await expect(page.locator("text=2026-07-13")).toBeVisible();  // Due date
  
  // No NaN, no empty chart, no sample data
  await expect(page.locator("text=NaN")).not.toBeVisible();
});
```

---

## Part 7: Definition of Done (Per Phase, Enforced at PR Review)

### Checklist (All Phases)

- [ ] **`pytest` green** — all new tests pass, existing tests updated
- [ ] **Independent recompute script** — `backend/scripts/verify_numbers.py` reads seed JSON + source PDFs, re-derives all headline numbers, prints pass/fail table (run before submit)
- [ ] **Playwright screenshots** — desktop + mobile (1 viewport) for every page touched
- [ ] **No console errors** — dev tools clean
- [ ] **No NaN / undefined rendered** — full click-through, every page
- [ ] **No dead nav links** — all nav items clickable
- [ ] **PR description** — every user-visible number traced: file + line + source
- [ ] **Branch discipline** — feature branch, PR as **draft**, no self-merge

---

## Part 8: Lead Review Gauntlet (What Happens to Your PR)

Know this in advance. Every returning PR gets:

### 1. Independent Recompute
Script (lead's tool; you do not modify):
```bash
python backend/scripts/lead_audit.py
```

Output: table of every displayed number vs. seed/PDF recompute. **Any FAIL blocks merge.** Run it yourself first:
```bash
python backend/scripts/lead_audit.py --trace --verbose
```

### 2. Number Tracing
Spot-check: sample of 5 rendered figures → API response → database → seed JSON → source PDF.  
**One untraceable number = PR fails.**

### 3. Adversarial Data (Import Gate Only)
Test with hostile CSVs:
- Line math off by $0.01
- Fee line labeled as product
- Unknown SKU
- Duplicate invoice #
- Invoice total doesn't foot

Silent acceptance of any = **PR fails.**

### 4. Empty-State Sweep
Fresh database, every route clicked:
- No `NaN`, no zeros-as-data
- Every empty state names missing input
- No sample content

### 5. Regression Guard
The 23-row trusted pool, its by-supplier split, and switching-savings figure must be **identical before/after** unless PR explicitly claims to change them (with source-level reason in description).

---

## Part 9: Out of Scope (Do Not Build Yet)

- Menu-engineering analytics on synthetic data (purged; waits for real Toast PMIX)
- Multi-tenant onboarding, billing, auth changes
- Annualized projections from single invoice (forbidden until ≥2 invoices; see §5.2)
- Shoreline vs US Foods/Shamrock price comparison (different product mix; scoped out; keep Shoreline as reference catalog + §5.4 internal spreads only)

---

## Appendix A: Data Source Provenance

| Source | Lead Audit Date | Format | Location |
|---|---|---|---|
| US Foods Order Guide 2026 (188 rows) | 2026-07-10 | PDF | `docs/source/US_Foods_Order_Guide_2026.pdf` |
| Shoreline Order Guide (129 items) | 2026-07-10 | PDF | `docs/source/Order_Guide_Shoreline.pdf` |
| US Foods vs Shamrock comparison | 2026-07-10 | JSON (seed) | `backend/app/seed/data/us_foods_vs_shamrock.json` |
| US Foods invoice #5022857 (06/04/2026) | TBD | PDF scans (Google Drive) | Shared folder: "Tempe Food Purchase Comparison" |
| Shoreline invoice #2027803 (04/03/2026) | TBD | PDF scans (Google Drive) | Shared folder: "Tempe Food Purchase Comparison" |
| Engagement plan (real proposal) | 2026-07-08 | Markdown + JSON | `backend/app/seed/snakes_and_lattes.py` |

---

## Appendix B: FAQ

**Q: Can I hardcode an example number in the UI while waiting for real data?**  
A: No. Empty state only. The Accuracy Contract forbids invented numbers.

**Q: What if the PDF extraction returns different numbers than the seed JSON?**  
A: Flag it in a pytest and raise in PR comments. Do not silently "fix" the PDF.

**Q: Do I need to implement all 8 truth surfaces at once?**  
A: No. Phases 3.1–3.8 are sequential. Ship one per PR, each with its own verification script.

**Q: What happens if an invoice line fails the validation gate?**  
A: It lands in `data_quality_flags`, is quarantined out of aggregates, and waits in the review UI for operator action.

**Q: Can I annualize from a single invoice?**  
A: No (§5.2). Annualization only with ≥2 invoices spanning ≥30 days. Before that, per-invoice actuals only.

