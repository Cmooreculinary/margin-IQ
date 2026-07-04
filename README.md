# Margin IQ

Menu profitability intelligence for multi-location restaurant, cafe, and
entertainment-dining operators. Margin IQ finds the basis points a menu is
hiding — item by item, location by location — using **Prime Cost** (food +
labor + packaging), not food cost alone. Nothing changes without operator
approval.

> Margin IQ — Your menu is hiding money. We surface it. You approve every move.

## What's built

This build covers **Phases 0–3** of the master roadmap end to end, plus a
seeded demo, with the data model and routes structured so Phases 4–6 extend
without rework:

| Phase | Status |
|---|---|
| 0 — Recon / schema design | done (this repo) |
| 1 — Ingestion + Prime Cost engine | done — Toast adapter, reconciliation gate, PLU exclusions, labor calibration |
| 2 — Analysis | done — quadrants, Pareto, seasonality matrix, competitor entry |
| 3 — Recommendations + approval + pro forma ticker | done |
| 4 — Portal, deliverable decks, exports | done — XLSX exports + watermarked PDF Analysis & Recommendations decks; remaining decks (Brand/Location Strategic Plans, Seasonality Matrix, Validation Deck) not yet built |
| 5 — Validation engine, P&L bridge, offset % | done — immutable signed baseline lock, post-period measurement adjusted for documented seasonality + food inflation, exactly-reconciling P&L bridge, item-level bridge, Offset % metric |
| 6 — Franchise mode, monitoring tiers | not started — `monitoring_tier` already modeled on `tenants`; franchisor/franchisee hierarchy not implemented |

**Demo dataset:** *Snakes & Lattes - US*, a three-location full-scale test
account built from the July 2026 proposal scope: Chicago, Tempe, and Tucson,
~$5M combined annualized F&B revenue, Tempe summer-slow / Nov-Apr peak
seasonality, a $6 Game Table Cover Fee PLU excluded from prime-cost math, and
deliberate labor-heavy food-cost mirage items so the Prime Cost story demos
itself the moment you look at the item table. The seed also includes an
Oct-Dec 2026 post-implementation period with selected price moves realized, so
the Validation page demos end-to-end: lock the Apr-Jun baseline, measure the
post period, and watch the P&L bridge and Offset % populate from realistic
data. The portal includes an Engagement Plan page with the timeline, data
requirements, deliverables, terms, and franchise-system test angle.

## Architecture

```
backend/   FastAPI + Motor (MongoDB) — ingestion, prime cost engine, analysis,
           recommendations/approval workflow, XLSX exports
frontend/  React + TypeScript + Vite + Tailwind (Trench Design tokens)
```

**Multi-tenancy**: every collection is scoped by `tenant_id`; every route
resolves a bearer token to exactly one tenant (`app/auth.py`) and every query
downstream filters on it. There is no cross-tenant read path.

**Data-quality gate**: `POST /ingestion/reconcile` must pass before any
analysis endpoint (`/items`, `/recommendations/generate`, `/dashboard/*`) will
serve data for a location — see `app/services/gate.py`. PMIX revenue must tie
out to reported financials within a configurable tolerance (default 2%).

**Adapter-based ingestion**: `app/adapters/base.py` defines the POS adapter
interface; `app/adapters/toast.py` is the v1 implementation. Square, Clover,
and Lightspeed adapters drop in without touching the ingestion pipeline,
reconciliation, or prime cost engine.

**Prime Cost engine** (`app/services/prime_cost.py`): computes food + labor +
packaging cost per item, contribution margin in $ and %, and flags the
"food-cost mirage" — items with a strong food-cost margin but a poor
prime-cost margin once labor is allocated in.

**Labor allocation** (`app/services/labor_allocation.py`): spreads a
location's actual labor cost across items by prep-complexity tier
(simple/moderate/complex, weights 0.7/1.0/1.6 by default) × daypart volume.
Fully operator-editable via `labor_matrix.complexity_weights`.

**Menu engineering** (`app/services/menu_engineering.py`): Star/Plowhorse/
Puzzle/Dog quadrant classification on median popularity × median CM$, Pareto
views for revenue and margin (deliberately separate lists — they diverge),
season assignment/indexing, and competitor price-position benchmarking.

**Recommendations + pro forma** (`app/services/recommendations.py`,
`pro_forma.py`): heuristic, transparent recommendation engine — plowhorses get
a capped surgical price increase (max +12%, never a broad hike), puzzles get
reposition/bundle recs, dogs get kill recs, food-cost-mirage items get a
reengineer rec regardless of quadrant. Every price rec carries a rationale,
projected BPS lift, and a PMIX offset from an editable elasticity assumption
per quadrant. The pro forma ticker sums cash impact for `approved`/`modified`
recommendations only, at brand and location level.

## Deploying on Render

The repo ships a `render.yaml` blueprint that deploys Margin IQ as a **single
web service**: the production `Dockerfile` builds the React portal and serves
it from the FastAPI process (same origin — no CORS, one free instance).

1. **Database** — Render doesn't host MongoDB, so create a free MongoDB Atlas
   cluster (M0) at https://cloud.mongodb.com: add a database user, allow
   network access from `0.0.0.0/0` (or Render's outbound IPs), and copy the
   `mongodb+srv://...` connection string.
2. **Deploy** — in the Render dashboard: **New → Blueprint**, connect this
   GitHub repo, pick the `claude/margin-iq-platform-7oov21` branch (or `main`
   once merged). Render reads `render.yaml` and prompts for `MONGO_URL` —
   paste the Atlas string.
3. **Demo data** — `SEED_DEMO=true` (the blueprint default) seeds the
   Snakes & Lattes US demo tenant on first boot when that tenant is missing.
   The deployed portal works immediately with the demo token. Set it to
   `false` for a real engagement.
4. Health check is `/health`; the portal is at `/`, interactive API docs at
   `/docs`.

Free-tier note: Render free web services sleep after inactivity and Atlas M0
is capped at 512 MB — both are fine for a demo; upgrade plans for production.

## Running locally

### Docker (recommended)
```bash
docker compose up
```
- API: http://localhost:8000/docs
- Frontend: http://localhost:5173

### Manual
```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # point MONGO_URL at a running Mongo instance
uvicorn app.main:app --reload

# Seed the Snakes & Lattes demo tenant
python -m app.seed.snakes_and_lattes
# prints the tenant's API token -- use it as: Authorization: Bearer <token>

# Frontend
cd frontend
npm install
npm run dev
```

The frontend defaults to the seed script's demo token
(`snakes-lattes-demo-token`) via `src/lib/api.ts` so it works out of the box
against a freshly seeded backend.

### Tests
```bash
cd backend
source .venv/bin/activate
python -m pytest -q
```
Unit tests cover the prime cost engine, labor allocation, reconciliation,
menu engineering, recommendations, and the pro forma ticker as pure functions
(no DB required). `tests/test_seed_integration.py` and `tests/test_api_smoke.py`
run the seed script and the full FastAPI app against an in-memory Mongo
(`mongomock-motor`) to verify the whole stack together — auth, gate,
analysis, approval, and XLSX export.

## API surface

| Route | Purpose |
|---|---|
| `POST /ingestion/pmix` | Upload a Toast PMIX export (CSV/XLSX) for a location/period |
| `POST /ingestion/financials` | Upload reported gross sales / food / labor cost for a period |
| `POST /ingestion/labor-matrix` | Set labor hours + blended rate + complexity weights per daypart |
| `POST /ingestion/menu-items/{plu}/exclude` | Tag a non-F&B PLU (cover fee, retail) as excluded |
| `POST /ingestion/reconcile` | Run the reconciliation gate for a location/period |
| `GET /items` | Item analysis table (prime cost, CM$/%, quadrant, mirage flag) — gated |
| `GET /items/pareto` | Revenue vs. margin Pareto (separate 80% lists) — gated |
| `GET /items/export.xlsx` | Watermarked XLSX export of the item table |
| `POST /recommendations/generate` | Generate the pending recommendation queue for a location |
| `POST /recommendations/{id}/decide` | Approve / modify / deny a recommendation |
| `GET /recommendations/pro-forma` | Running cumulative cash-flow ticker |
| `GET /dashboard/brand` / `GET /dashboard/location/{id}` | KPI roll-ups |
| `POST /validation/baseline/lock` | Lock the immutable, digitally-acknowledged 90-day baseline |
| `POST /validation/measure` | Post-implementation measurement: P&L bridge, validated BPS lift, Offset % |
| `GET /exports/analysis-deck.pdf` / `GET /exports/recommendations-deck.pdf` | Watermarked PDF deliverable decks |

Full interactive docs at `/docs` once the backend is running.

## Guardrails honored

- Approval-driven: the system never changes a price, only recommends. Every
  decision writes an `approval_log` entry (who, when, original rec vs. final).
- Never analyzes unreconciled data silently (`require_reconciled` gate).
- No broad price hikes — recommendations cap at +12% and round to the nearest
  quarter, with a floor check so a rounding pass never collapses an increase
  back to the sticker price.
- Tenant isolation is absolute; exports are watermarked with tenant + export
  timestamp.
- No customer PII is modeled or stored — PMIX and cost data only.
