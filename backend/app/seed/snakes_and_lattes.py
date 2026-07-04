"""Seed data for the Snakes & Lattes US demo tenant.

The dataset turns the July 2026 proposal into a functional full-scale Margin IQ
test account: three US locations, a brand-wide menu master, Toast-style PMIX,
financial reconciliation, labor allocation, game-fee PLU exclusion,
recommendations, post-implementation validation actuals, and the engagement
timeline / needs / deliverables plan used by the portal.

Run directly:
    python -m app.seed.snakes_and_lattes
"""
from __future__ import annotations

import asyncio
import statistics
from datetime import datetime, timezone

from app.services.menu_engineering import classify_quadrants
from app.services.pipeline import build_location_item_metrics
from app.services.reconciliation import compute_pos_total, reconcile
from app.services.recommendations import generate_recommendations
from app.utils import new_id

DEMO_TENANT_TOKEN = "snakes-lattes-demo-token"
TENANT_SLUG = "snakes-and-lattes-us"

PERIOD_START = datetime(2026, 4, 1, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 6, 30, tzinfo=timezone.utc)

POST_PERIOD_START = datetime(2026, 10, 1, tzinfo=timezone.utc)
POST_PERIOD_END = datetime(2026, 12, 31, tzinfo=timezone.utc)

SEASONS = [
    {"name": "Peak Season", "start_month": 11, "end_month": 4},
    {"name": "Summer Slow", "start_month": 5, "end_month": 10},
]

LOCATIONS = [
    {
        "code": "TMP",
        "name": "Tempe, AZ - Flagship",
        "sqft": 7500,
        "target_q2_fnb_revenue": 675000,
        "post_season_factor": 1.12,
        "labor_rate": 26.0,
        "labor_hours": {"brunch": 1380, "dinner": 4920, "all_day": 1080},
        "concept_notes": (
            "Franchise model location. Two patios, brunch seven days, 85% night mix, "
            "roughly 50% food / 30% alcohol, material Nov-Apr peak season."
        ),
        "daypart_hours": {"brunch": "10:00-15:00", "dinner": "15:00-23:00", "all_day": "10:00-00:00"},
    },
    {
        "code": "CHI",
        "name": "Chicago, IL",
        "sqft": 6100,
        "target_q2_fnb_revenue": 462500,
        "post_season_factor": 1.05,
        "labor_rate": 28.0,
        "labor_hours": {"brunch": 620, "dinner": 3180, "all_day": 720},
        "concept_notes": (
            "Basement and private rooms, weekend daytime only, growing private event stream, "
            "unique footprint relative to the Tempe franchise model."
        ),
        "daypart_hours": {"brunch": "11:00-15:00 weekends", "dinner": "15:00-23:00", "all_day": "11:00-00:00"},
    },
    {
        "code": "TUC",
        "name": "Tucson, AZ",
        "sqft": 2300,
        "target_q2_fnb_revenue": 112500,
        "post_season_factor": 1.02,
        "labor_rate": 24.0,
        "labor_hours": {"brunch": 260, "dinner": 980, "all_day": 260},
        "concept_notes": (
            "Smaller footprint below the 5,000 sq ft franchise model minimum. "
            "Currently underperforming with a high need for menu optimization."
        ),
        "daypart_hours": {"brunch": "10:00-14:00 weekends", "dinner": "16:00-22:00", "all_day": "10:00-23:00"},
    },
]

# Brand-wide master catalog. Baseline units below are scaled per location to
# hit the proposal's approximate US F&B revenue mix. The game fee remains
# visible in PMIX records but is excluded from prime-cost math.
ITEM_CATALOG = [
    # plu, name, category, daypart, complexity, price, food_cost, packaging, base_units
    ("1001", "Classic Burger", "Mains", "dinner", "moderate", 17.00, 5.95, 0.35, 3600),
    ("1002", "Chicken Tenders & Fries", "Mains", "dinner", "moderate", 16.00, 7.75, 0.35, 5200),
    ("1003", "Vegan Buddha Bowl", "Mains", "dinner", "simple", 15.00, 4.20, 0.30, 1800),
    ("1004", "Mac & Cheese", "Mains", "dinner", "complex", 14.00, 3.50, 0.30, 2400),
    ("1005", "Brunch Burrito", "Mains", "brunch", "moderate", 15.00, 4.50, 0.30, 2600),
    ("1006", "Quebec Poutine", "Mains", "dinner", "complex", 13.00, 3.25, 0.30, 3800),
    ("2001", "Loaded Nachos", "Appetizers", "dinner", "complex", 16.00, 4.25, 0.35, 4100),
    ("2002", "Soft Pretzels", "Appetizers", "dinner", "simple", 10.00, 5.10, 0.18, 5200),
    ("2003", "Wings", "Appetizers", "dinner", "moderate", 17.00, 6.10, 0.30, 3300),
    ("2004", "Hummus Board", "Appetizers", "dinner", "simple", 12.00, 3.10, 0.25, 1800),
    ("4001", "Brownie Sundae", "Desserts", "dinner", "simple", 9.00, 2.10, 0.18, 2200),
    ("4002", "Churros", "Desserts", "dinner", "simple", 8.00, 1.60, 0.15, 2000),
    ("3001", "Local Draft Beer", "Drinks", "all_day", "simple", 8.00, 1.45, 0.08, 11000),
    ("3002", "House Cocktail", "Drinks", "all_day", "moderate", 13.00, 3.00, 0.12, 7000),
    ("3003", "Wine Pour", "Drinks", "all_day", "simple", 11.00, 2.80, 0.10, 3600),
    ("3004", "Craft Mocktail", "Drinks", "all_day", "moderate", 8.00, 1.10, 0.12, 2800),
    ("3005", "Coffee / Espresso", "Drinks", "brunch", "simple", 5.00, 0.80, 0.08, 4200),
    ("9001", "Game Table Cover Fee", "Fees", "all_day", "simple", 6.00, 0.00, 0.00, 30000),
]

EXCLUDED_PLUS = {"9001"}

IMPLEMENTED_PRICE_BUMPS = {
    "1002": 0.75,
    "1006": 0.75,
    "2002": 0.50,
    "3001": 0.50,
    "3002": 1.00,
    "3004": 0.25,
}
ELASTICITY_DIP = 0.985

COMPETITORS_BY_LOCATION = {
    "TMP": [
        ("Culinary Dropout Tempe", "Classic Burger", 18.50),
        ("Pedal Haus Brewery", "Local Draft Beer", 8.50),
        ("Cornish Pasty Co", "Quebec Poutine", 14.00),
        ("Postino Annex", "House Cocktail", 13.50),
    ],
    "CHI": [
        ("Kaiser Tiger", "Classic Burger", 18.00),
        ("The Gage", "Wine Pour", 12.00),
        ("Emporium Arcade Bar", "Local Draft Beer", 8.00),
        ("Beatrix Loop", "Brunch Burrito", 16.00),
    ],
    "TUC": [
        ("The Monica", "Classic Burger", 16.50),
        ("Ermanos Bar", "Local Draft Beer", 7.50),
        ("Reilly Craft Pizza", "House Cocktail", 13.00),
        ("Tumerico", "Vegan Buddha Bowl", 14.00),
    ],
}

ENGAGEMENT_PLAN = {
    "proposal_month": "July 2026",
    "engagement_start": "TBD, upon execution of agreement",
    "scope": {
        "client": "Snakes & Lattes",
        "locations": ["Chicago, IL", "Tempe, AZ", "Tucson, AZ"],
        "excluded_scope": ["Canadian locations"],
        "annual_fnb_revenue_estimate": 5000000,
        "target_roi_payback_days": 30,
        "delivery_window": "2-3 weeks from complete, validated data receipt",
        "guardrails": [
            "Surgical recommendations only; no broad price hikes.",
            "Every item-level move requires operator approve / modify / deny.",
            "Game fee PLU is visible in PMIX but excluded from F&B prime-cost math.",
            "Forecasted lift and validated results are clearly separated.",
        ],
    },
    "timeline": [
        {
            "phase": "I",
            "name": "Baseline & Validation Design",
            "timing": "Days 0-2 after agreement execution",
            "needs": [
                "Confirm three-location US scope and Canadian exclusion.",
                "Confirm 90-day baseline period and post-implementation validation period.",
                "Confirm Tempe summer slow / Nov-Apr peak seasonality assumptions.",
            ],
            "deliverables": [
                "Signed baseline and validation period design.",
                "Treatment/control measurement plan.",
                "Seasonality rule set for the validation engine.",
            ],
        },
        {
            "phase": "II",
            "name": "Data Ingestion & Calibration",
            "timing": "Days 2-7 after complete data package",
            "needs": [
                "90-day Toast PMIX export per US location.",
                "Recipe cost by PLU / menu item.",
                "Location financials with gross sales, food cost, and labor cost.",
                "Labor matrix by location and daypart.",
                "Game / cover fee PLU confirmation.",
            ],
            "deliverables": [
                "Toast PMIX import and reconciliation gate.",
                "PLU exclusion map for non-F&B revenue.",
                "Labor allocation calibration by location.",
                "Data quality exceptions, if any, in plain English.",
            ],
        },
        {
            "phase": "III",
            "name": "Analysis",
            "timing": "Days 7-12",
            "needs": [
                "Comparable F&B competitor list with addresses near each US location.",
                "Operator review of any category or daypart mapping exceptions.",
            ],
            "deliverables": [
                "Prime-cost item table by location.",
                "Star / Plowhorse / Puzzle / Dog classification.",
                "Revenue and margin Pareto views.",
                "F&B competitor pricing benchmark.",
                "Location strategic snapshots for Chicago, Tempe, and Tucson.",
            ],
        },
        {
            "phase": "IV",
            "name": "Recommendations & Client Approval",
            "timing": "Days 12-15 plus on-site review scheduling",
            "needs": [
                "Designated F&B / operations SME for review.",
                "Client approval decisions in portal: approve, modify, or deny.",
                "HQ review availability for final action-set walkthrough.",
            ],
            "deliverables": [
                "Item-level pricing and menu-architecture recommendations.",
                "Live running pro forma ticker.",
                "Approved implementation checklist.",
                "Analysis Deck and Recommendations Deck.",
            ],
        },
        {
            "phase": "V",
            "name": "Validation",
            "timing": "60-90 days after updated menu launch",
            "needs": [
                "Post-implementation PMIX exports.",
                "Updated food cost inflation assumptions.",
                "Documentation of seasonality or operating changes during the test window.",
            ],
            "deliverables": [
                "P&L bridge: projected vs. actual.",
                "Treatment/control results.",
                "Validated BPS lift.",
                "DDD Offset % metric.",
                "Validation Deck.",
            ],
        },
    ],
    "data_requirements": [
        "90-day Toast POS PMIX export per location",
        "Location financial statements: gross sales, food cost, labor cost",
        "F&B competitor list with addresses near Chicago, Tempe, and Tucson",
        "Recipe cost data by PLU / menu item",
        "Labor matrix: hours and rates by location and daypart",
        "Designated F&B / operations SME for kickoff and review sessions",
    ],
    "deliverables": [
        {"name": "Analysis Deck", "category": "Analysis & Recommendations", "status": "Included"},
        {"name": "Recommendations Deck", "category": "Analysis & Recommendations", "status": "Included"},
        {"name": "Brand Strategic Plan", "category": "Analysis & Recommendations", "status": "Included"},
        {"name": "Location Strategic Plans", "category": "Analysis & Recommendations", "status": "Included"},
        {"name": "Seasonality Matrix", "category": "Analysis & Recommendations", "status": "Included"},
        {"name": "Validation Deck", "category": "Validation", "status": "Post-launch"},
        {"name": "DDD Offset % Metric", "category": "Validation", "status": "Post-launch"},
        {"name": "Brand & Location Pro Formas", "category": "Data & Portal", "status": "Included"},
        {"name": "XLSX Data Exports", "category": "Data & Portal", "status": "Included"},
        {"name": "Client Portal Access", "category": "Data & Portal", "status": "12 months"},
    ],
    "terms": {
        "project_fee": 9900,
        "payment_structure": "50% at execution / 50% at final delivery",
        "invoice_1": 4950,
        "invoice_2": 4950,
        "delivery_window": "2-3 weeks from complete data receipt",
        "onsite_review": "One HQ recommendation-review trip; economy travel billed at cost with prior approval.",
        "optional_monitoring": [
            "Essential: monthly PMIX snapshot, margin trend dashboard, competitor price tracking.",
            "Professional: Essential plus tune-up recommendations, BOH labor efficiency dashboard, feedback refresh.",
            "Executive: Professional plus quarterly strategic review deck and new-item profit modeling.",
        ],
    },
    "franchise_angle": [
        "Tempe is the franchise model location and should be optimized before replication.",
        "Validated basis-point lift can support internal Item 19 / FDD data work without legal-claim language.",
        "A recurring annual menu review creates a system-wide franchisee profitability loop.",
        "A tighter menu is easier to train, staff, and execute across franchised units.",
    ],
}


def _base_fnb_revenue() -> float:
    return sum(price * base_units for plu, _, _, _, _, price, _, _, base_units in ITEM_CATALOG if plu not in EXCLUDED_PLUS)


async def seed(db) -> dict:
    existing = await db.tenants.find_one({"slug": TENANT_SLUG})
    if existing:
        if not await db.engagement_plans.find_one({"tenant_id": existing["_id"]}):
            await db.engagement_plans.insert_one(
                {
                    "_id": new_id(),
                    "tenant_id": existing["_id"],
                    "brand_name": "Snakes & Lattes",
                    **ENGAGEMENT_PLAN,
                    "created_at": datetime.now(timezone.utc),
                }
            )
        locations = await db.locations.find({"tenant_id": existing["_id"]}).to_list(length=None)
        return {
            "tenant_id": existing["_id"],
            "api_token": existing["api_token"],
            "location_ids": {loc["code"]: loc["_id"] for loc in locations},
        }

    tenant_id = new_id()
    await db.tenants.insert_one(
        {
            "_id": tenant_id,
            "name": "Snakes & Lattes - US",
            "slug": TENANT_SLUG,
            "api_token": DEMO_TENANT_TOKEN,
            "monitoring_tier": "professional",
            "created_at": datetime.now(timezone.utc),
        }
    )

    await db.engagement_plans.insert_one(
        {
            "_id": new_id(),
            "tenant_id": tenant_id,
            "brand_name": "Snakes & Lattes",
            **ENGAGEMENT_PLAN,
            "created_at": datetime.now(timezone.utc),
        }
    )

    for plu, name, category, daypart, complexity, price, food_cost, packaging, _ in ITEM_CATALOG:
        await db.menu_items.insert_one(
            {
                "_id": new_id(),
                "tenant_id": tenant_id,
                "location_id": None,
                "plu": plu,
                "name": name,
                "category": category,
                "daypart": daypart,
                "prep_complexity": complexity,
                "price": price,
                "recipe_food_cost": food_cost,
                "packaging_cost": packaging,
                "is_excluded": plu in EXCLUDED_PLUS,
            }
        )

    location_ids: dict[str, str] = {}
    base_revenue = _base_fnb_revenue()
    for loc in LOCATIONS:
        location_id = new_id()
        location_ids[loc["code"]] = location_id
        await db.locations.insert_one(
            {
                "_id": location_id,
                "tenant_id": tenant_id,
                "name": loc["name"],
                "code": loc["code"],
                "sqft": loc["sqft"],
                "concept_notes": loc["concept_notes"],
                "daypart_hours": loc["daypart_hours"],
                "seasons": SEASONS,
                "annualized_fnb_revenue_estimate": loc["target_q2_fnb_revenue"] * 4,
            }
        )

        scale = loc["target_q2_fnb_revenue"] / base_revenue
        pmix_docs = []
        pos_total_fnb = 0.0
        for plu, name, category, daypart, complexity, price, food_cost, packaging, base_units in ITEM_CATALOG:
            units = max(round(base_units * scale), 1)
            revenue = round(units * price, 2)
            if plu not in EXCLUDED_PLUS:
                pos_total_fnb += revenue
            pmix_docs.append(
                {
                    "_id": new_id(),
                    "tenant_id": tenant_id,
                    "location_id": location_id,
                    "plu": plu,
                    "item_name": name,
                    "period_start": PERIOD_START,
                    "period_end": PERIOD_END,
                    "units_sold": units,
                    "gross_revenue": revenue,
                    "source": "toast",
                }
            )
        await db.pmix_records.insert_many(pmix_docs)

        post_pmix_docs = []
        post_pos_total_fnb = 0.0
        for plu, name, category, daypart, complexity, price, food_cost, packaging, base_units in ITEM_CATALOG:
            bump = IMPLEMENTED_PRICE_BUMPS.get(plu, 0.0)
            realized_price = price + bump
            units = max(round(base_units * scale * loc["post_season_factor"] * (ELASTICITY_DIP if bump else 1.0)), 1)
            revenue = round(units * realized_price, 2)
            if plu not in EXCLUDED_PLUS:
                post_pos_total_fnb += revenue
            post_pmix_docs.append(
                {
                    "_id": new_id(),
                    "tenant_id": tenant_id,
                    "location_id": location_id,
                    "plu": plu,
                    "item_name": name,
                    "period_start": POST_PERIOD_START,
                    "period_end": POST_PERIOD_END,
                    "units_sold": units,
                    "gross_revenue": revenue,
                    "source": "toast",
                }
            )
        await db.pmix_records.insert_many(post_pmix_docs)

        await db.labor_matrix.insert_many(
            [
                {
                    "_id": new_id(),
                    "tenant_id": tenant_id,
                    "location_id": location_id,
                    "daypart": daypart,
                    "hours": hours,
                    "blended_rate": loc["labor_rate"],
                    "complexity_weights": {"simple": 0.7, "moderate": 1.0, "complex": 1.65},
                }
                for daypart, hours in loc["labor_hours"].items()
            ]
        )

        reported_gross_sales = round(pos_total_fnb * 1.003, 2)
        await db.financials.insert_one(
            {
                "_id": new_id(),
                "tenant_id": tenant_id,
                "location_id": location_id,
                "period_start": PERIOD_START,
                "period_end": PERIOD_END,
                "gross_sales": reported_gross_sales,
                "food_cost_actual": round(pos_total_fnb * 0.31, 2),
                "labor_cost_actual": round(
                    sum(loc["labor_hours"].values()) * loc["labor_rate"], 2
                ),
            }
        )

        recon = reconcile(
            location_id=location_id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            pos_total=compute_pos_total(pmix_docs, exclude_plus=EXCLUDED_PLUS),
            reported_gross_sales=reported_gross_sales,
            tolerance_pct=2.0,
        )
        recon_doc = dict(recon)
        recon_doc["_id"] = new_id()
        recon_doc["tenant_id"] = tenant_id
        recon_doc["run_at"] = datetime.now(timezone.utc)
        await db.reconciliation_runs.insert_one(recon_doc)

        post_reported = round(post_pos_total_fnb * 1.002, 2)
        await db.financials.insert_one(
            {
                "_id": new_id(),
                "tenant_id": tenant_id,
                "location_id": location_id,
                "period_start": POST_PERIOD_START,
                "period_end": POST_PERIOD_END,
                "gross_sales": post_reported,
                "food_cost_actual": round(post_pos_total_fnb * 0.325, 2),
                "labor_cost_actual": round(
                    sum(loc["labor_hours"].values()) * loc["labor_rate"] * loc["post_season_factor"], 2
                ),
            }
        )

        post_recon = reconcile(
            location_id=location_id,
            period_start=POST_PERIOD_START,
            period_end=POST_PERIOD_END,
            pos_total=compute_pos_total(post_pmix_docs, exclude_plus=EXCLUDED_PLUS),
            reported_gross_sales=post_reported,
            tolerance_pct=2.0,
        )
        post_recon_doc = dict(post_recon)
        post_recon_doc["_id"] = new_id()
        post_recon_doc["tenant_id"] = tenant_id
        post_recon_doc["run_at"] = datetime.now(timezone.utc)
        await db.reconciliation_runs.insert_one(post_recon_doc)

        await db.competitors.insert_many(
            [
                {
                    "_id": new_id(),
                    "tenant_id": tenant_id,
                    "location_id": location_id,
                    "competitor_name": competitor_name,
                    "item_name": item_name,
                    "price": price,
                }
                for competitor_name, item_name, price in COMPETITORS_BY_LOCATION[loc["code"]]
            ]
        )

    for location_id in location_ids.values():
        items = await build_location_item_metrics(
            db,
            tenant_id=tenant_id,
            location_id=location_id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
        )
        if not items:
            continue

        location = await db.locations.find_one({"_id": location_id})
        quadrant_by_plu = {q.plu: q.quadrant for q in classify_quadrants(items)}
        revenue_baseline = sum(i.revenue for i in items)
        median_prime_cost_pct = statistics.median(i.prime_cost_pct for i in items)
        recs = generate_recommendations(
            items,
            quadrant_by_plu,
            location_revenue_baseline=revenue_baseline,
            location_median_prime_cost_pct=median_prime_cost_pct,
        )

        item_by_plu = {i.plu: i for i in items}
        docs = []
        for rec in recs:
            item = item_by_plu[rec["plu"]]
            doc = dict(rec)
            doc["_id"] = new_id()
            doc["tenant_id"] = tenant_id
            doc["location_id"] = location_id
            doc["location_name"] = location["name"]
            doc["status"] = "pending"
            doc["created_at"] = datetime.now(timezone.utc)
            doc["decided_by"] = None
            doc["decided_at"] = None
            doc["final_price"] = None
            doc["_prime_cost"] = item.prime_cost
            doc["_units_sold"] = item.units_sold
            doc["_elasticity"] = -0.6
            doc["_location_revenue_baseline"] = revenue_baseline
            docs.append(doc)
        if docs:
            await db.recommendations.insert_many(docs)

    return {"tenant_id": tenant_id, "api_token": DEMO_TENANT_TOKEN, "location_ids": location_ids}


async def _main():
    from app.db import get_database

    db = get_database()
    result = await seed(db)
    print("Seeded Snakes & Lattes US demo tenant.")
    print(f"  tenant_id:  {result['tenant_id']}")
    print(f"  api_token:  {result['api_token']}  (use as: Authorization: Bearer <token>)")
    print(f"  locations:  {result['location_ids']}")


if __name__ == "__main__":
    asyncio.run(_main())
