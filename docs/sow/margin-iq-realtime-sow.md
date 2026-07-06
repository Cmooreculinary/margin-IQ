# Statement of Work — Margin IQ Real-Time Deployment

| | |
|---|---|
| **Project** | Margin IQ — Real-Time Menu Profitability Monitoring |
| **Document date** | July 6, 2026 |
| **Prepared by** | Margin IQ (C. Moore) |
| **Prepared for** | ______________________________ ("Client") |
| **SOW version** | 1.0 |
| **Estimated engagement window** | 1–2 weeks from signature |

---

## 1. Background

Margin IQ is a menu-profitability intelligence platform for multi-location
restaurant, cafe, and entertainment-dining operators. It computes **Prime
Cost** (food + labor + packaging) per menu item, classifies items into
menu-engineering quadrants, flags "food-cost mirage" items, and generates
operator-approved pricing recommendations with a running pro forma cash-flow
ticker.

The platform as delivered today runs on a **batch cadence**: PMIX exports and
financials are uploaded per period, reconciled through the data-quality gate,
and then analyzed. This SOW covers standing the platform up for a
**real-time use case**, where sales and cost data flow in continuously and the
operator sees live margin intelligence rather than end-of-period reports.

## 2. Objective

Configure and deploy Margin IQ so that the Client's operation runs in
real time:

- POS sales data (Toast) ingested continuously rather than by periodic export.
- Dashboards, item analysis, and the pro forma ticker refreshed live as data
  arrives, with the reconciliation gate applied on a rolling basis.
- Document scanning (P&Ls, menus, PMIX reports, labor schedules, competitor
  menus) processed on arrival via the Claude-powered extraction pipeline, with
  operator review-then-commit preserved.
- The service hosted on an always-on paid instance (no cold starts, persistent
  database) suitable for production monitoring.

## 3. Scope of Work

### 3.1 In scope

1. **Environment provisioning** — deploy the Margin IQ blueprint
   (`render.yaml`) to a paid, always-on Render web service with a persistent
   disk; disable demo seeding (`SEED_DEMO=false`); configure the
   `ANTHROPIC_API_KEY` for document scanning.
2. **Real-time ingestion configuration** — configure the Toast adapter for
   continuous/scheduled ingestion into the existing pipeline (PMIX,
   financials, labor matrix), including PLU exclusions and rolling
   reconciliation against the data-quality gate.
3. **Tenant setup** — create the Client's production tenant, locations, labor
   matrix (complexity weights, dayparts), and API token; verify tenant
   isolation.
4. **GPU-accelerated document pipeline** — provision on-demand GPU compute for
   image/PDF pre-processing (deskew, denoise, page splitting) ahead of the
   Claude extraction step, sized for the Client's expected scan volume.
5. **Verification** — end-to-end smoke test: live ingestion → reconciliation
   pass → item analysis → recommendation generation → approval → pro forma
   ticker update; document scan → review → commit.
6. **Handoff** — walkthrough of the portal, credentials transfer, and a short
   runbook covering ingestion status, reconciliation failures, and key
   rotation.

### 3.2 Out of scope

- New feature development (e.g., Square/Clover/Lightspeed adapters, franchise
  mode / Phase 6, additional deliverable decks).
- Historical data backfill beyond one baseline period.
- Custom integrations not listed above; ongoing managed support beyond the
  handoff (available under a separate agreement).
- Third-party account creation fees or plan upgrades beyond the estimates in
  Section 5 (billed by the vendors directly to the Client).

## 4. Deliverables

| # | Deliverable | Acceptance criterion |
|---|---|---|
| D1 | Production Margin IQ instance on Render (always-on, persistent disk, demo seeding off) | `/health` returns healthy; data survives a restart |
| D2 | Client tenant configured with locations, labor matrix, and API token | Client can log into the portal and see own locations only |
| D3 | Real-time Toast ingestion running with rolling reconciliation | New sales visible in dashboards without manual upload; gate blocks unreconciled data |
| D4 | Document scanning live (GPU pre-processing + Claude extraction) | Uploaded P&L/menu image produces reviewable structured records; commit lands in the correct collections |
| D5 | Handoff runbook and walkthrough | Delivered as markdown in the repo; walkthrough session completed |

## 5. Pricing

### 5.1 Professional services (one-time)

| Item | Hours | Rate | Total |
|---|---:|---:|---:|
| Deployment, configuration, verification, and handoff (Sections 3.1.1–3.1.6) | 5 | $25.00/hr | **$125.00** |

### 5.2 Recurring infrastructure and usage charges (estimated, monthly)

These services are billed by their vendors directly to the Client. Figures
are good-faith estimates at current published pricing and the stated usage
assumptions; actual charges vary with usage and vendor price changes.

| Item | Assumption | Est. monthly |
|---|---|---:|
| Render web service (Standard instance, always-on) | Required for real-time: no sleep-on-idle, supports persistent disk | $25.00 |
| Render persistent disk | 1 GB SQLite volume at $0.25/GB-month | $0.25 |
| GPU compute (on-demand) | Document pre-processing / OCR acceleration; ~20 hrs/month of an entry-level cloud GPU (T4/L4 class) at ~$0.60/hr | $12.00 |
| GitHub | Team plan, 1 seat ($4) + Actions/storage overage buffer | $8.00 |
| Claude API (document scanning) | Claude Opus 4.8 at $5.00 input / $25.00 output per million tokens; ~500 scans/month at ~3,000 input + ~1,500 output tokens per scan (≈ $0.05/scan) | $26.25 |
| **Estimated recurring total** | | **≈ $71.50/mo** |

### 5.3 Engagement total

| | |
|---|---:|
| One-time professional services | $125.00 |
| First-month estimated infrastructure/usage | ≈ $71.50 |
| **Estimated first-month total** | **≈ $196.50** |

Notes:

- Claude API spend scales linearly with scan volume; heavier months are
  billed at actual usage. Prompt caching and batch submission can reduce this
  if volume grows materially.
- GPU hours are on-demand — months with no scanning incur no GPU charge.
- If the Client already holds a GitHub plan or Anthropic account, those lines
  drop from the estimate.

## 6. Schedule

| Milestone | Target |
|---|---|
| SOW signed, accounts/keys provided by Client | Day 0 |
| D1–D2 (deploy + tenant) | Day 1–3 |
| D3–D4 (real-time ingestion + scanning live) | Day 3–7 |
| D5 (verification + handoff) | Day 7–10 |

The 5 professional-service hours are spread across these milestones; calendar
duration depends on Client turnaround for credentials and data access.

## 7. Client responsibilities

- Provide Toast POS access/exports, reported financials, and labor data for
  the baseline period.
- Provide or authorize creation of Render, GitHub, cloud-GPU, and Anthropic
  accounts, and accept direct billing for them.
- Designate an operator to review and commit scanned documents and to
  approve/deny pricing recommendations (the system never changes a price
  without operator approval).
- Respond to reconciliation-gate failures (data discrepancies > 2% tolerance)
  with corrected source data.

## 8. Assumptions and terms

- Work performed remotely. Hours beyond the 5-hour estimate require written
  approval at the same $25/hr rate before work continues.
- Invoicing: professional services invoiced on completion of D5; net 15.
- All data remains the Client's property; tenant isolation and watermarked
  exports per platform guardrails. No customer PII is modeled or stored —
  PMIX and cost data only.
- Either party may terminate with 7 days' written notice; hours worked to
  date are billable.
- Warranty: defects in the delivered configuration reported within 14 days of
  handoff are corrected at no charge.

## 9. Acceptance

| | Client | Provider |
|---|---|---|
| Name | ______________________ | ______________________ |
| Title | ______________________ | ______________________ |
| Signature | ______________________ | ______________________ |
| Date | ______________________ | ______________________ |
