"""Seed data for the demo tenant: Rook & Roast, a fictional 3-location
entertainment-dining brand (board-game cafes) with ~$5M combined annual F&B,
realistic seasonality, a cover-fee PLU to exclude, and one deliberately
labor-heavy 'food-cost mirage' item (Loaded Nachos) so the Prime Cost story
demos itself without any manual setup.

Run directly against the configured SQLite database:
    python -m app.seed.rook_and_roast

Or call `await seed(db)` against an injected database (e.g. in tests).
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

DEMO_TENANT_TOKEN = "rook-roast-demo-token"

PERIOD_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 3, 31, tzinfo=timezone.utc)

# Post-implementation period (Q2) for the validation-engine demo: the five
# plowhorse price recs are "implemented" (+$0.25 realized price), volumes carry
# the summer-slow seasonality plus a small elasticity dip on the changed items.
POST_PERIOD_START = datetime(2026, 4, 1, tzinfo=timezone.utc)
POST_PERIOD_END = datetime(2026, 6, 30, tzinfo=timezone.utc)
IMPLEMENTED_PRICE_BUMPS = {"2002": 0.25, "2003": 0.25, "3001": 0.25, "3003": 0.25, "3004": 0.25}
SUMMER_SLOW_FACTOR = 0.85  # documented seasonality: Q2 volume vs Q1 peak
ELASTICITY_DIP = 0.98  # extra -2% volume on repriced items

SEASONS = [
    {"name": "Peak Season", "start_month": 11, "end_month": 4},  # Nov-Apr: board-game cafe high season
    {"name": "Summer Slow", "start_month": 5, "end_month": 10},  # May-Oct
]

LOCATIONS = [
    {"code": "CHI", "name": "Chicago", "sqft": 6200, "concept_notes": "Flagship, dinner + late-night heavy", "multiplier": 1.3},
    {"code": "TMP", "name": "Tempe", "sqft": 4800, "concept_notes": "Campus-adjacent, strong weekend brunch", "multiplier": 1.0},
    {"code": "TUC", "name": "Tucson", "sqft": 3600, "concept_notes": "Smallest footprint, growing late-night", "multiplier": 0.7},
]

# Brand-wide master catalog (location_id=None). Price/recipe is shared across
# the chain; only PMIX volume and labor allocation vary by location.
ITEM_CATALOG = [
    # plu, name, category, daypart, prep_complexity, price, food_cost, packaging, base_units
    ("1001", "Wagyu Burger", "Mains", "dinner", "moderate", 18.00, 7.50, 0.40, 2100),
    ("1002", "Chicken Tender Basket", "Mains", "dinner", "moderate", 14.00, 4.20, 0.35, 2700),
    ("1003", "Veggie Power Bowl", "Mains", "dinner", "simple", 13.00, 3.90, 0.30, 900),
    ("1004", "BBQ Pulled Pork Sandwich", "Mains", "dinner", "moderate", 15.00, 5.25, 0.35, 1500),
    ("1005", "Margherita Flatbread", "Mains", "dinner", "simple", 12.00, 3.00, 0.25, 1200),
    ("2001", "Loaded Nachos", "Appetizers", "dinner", "complex", 13.00, 3.00, 0.30, 1200),  # food-cost mirage
    ("2002", "Pretzel Bites", "Appetizers", "dinner", "simple", 8.00, 1.80, 0.20, 2400),
    ("2003", "Mozzarella Sticks", "Appetizers", "dinner", "simple", 9.00, 2.25, 0.20, 1800),
    ("2004", "Truffle Parmesan Fries", "Appetizers", "dinner", "moderate", 11.00, 2.75, 0.25, 1500),
    ("2005", "Wings (12pc)", "Appetizers", "dinner", "moderate", 14.00, 4.90, 0.30, 1800),
    ("4001", "Molten Chocolate Cake", "Desserts", "dinner", "simple", 9.00, 2.25, 0.20, 1050),
    ("4002", "Churro Bites", "Desserts", "dinner", "simple", 7.00, 1.40, 0.15, 900),
    ("3001", "Craft Beer Draft", "Drinks", "all_day", "simple", 7.00, 1.20, 0.10, 9000),
    ("3002", "House Margarita", "Drinks", "all_day", "simple", 11.00, 2.50, 0.15, 5400),
    ("3003", "Fountain Soda", "Drinks", "all_day", "simple", 3.50, 0.30, 0.05, 7500),
    ("3004", "Cold Brew Coffee", "Drinks", "all_day", "simple", 4.50, 0.80, 0.10, 3600),
    ("3005", "Signature Cocktail", "Drinks", "all_day", "moderate", 12.00, 3.00, 0.20, 2700),
    ("9001", "Game Table Cover Fee", "Fees", "all_day", "simple", 5.00, 0.00, 0.00, 4500),
]
EXCLUDED_PLUS = {"9001"}

DINNER_LABOR_HOURS_BASE = 1400
ALL_DAY_LABOR_HOURS_BASE = 360
BLENDED_RATE = 25.0

COMPETITORS = [
    ("The Dice Tower Tavern", "Loaded Nachos", 12.50),
    ("Meeple's Pub", "Craft Beer Draft", 7.50),
    ("Board & Barrel", "Wagyu Burger", 19.50),
]


async def seed(db) -> dict:
    tenant_id = new_id()
    await db.tenants.insert_one(
        {
            "_id": tenant_id,
            "name": "Rook & Roast",
            "slug": "rook-and-roast",
            "api_token": DEMO_TENANT_TOKEN,
            "monitoring_tier": "professional",
            "created_at": datetime.now(timezone.utc),
        }
    )

    # Brand-wide menu master
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
                "daypart_hours": {"dinner": "16:00-23:00", "all_day": "11:00-01:00"},
                "seasons": SEASONS,
            }
        )

        multiplier = loc["multiplier"]

        # PMIX
        pmix_docs = []
        pos_total_fnb = 0.0
        for plu, name, category, daypart, complexity, price, food_cost, packaging, base_units in ITEM_CATALOG:
            units = round(base_units * multiplier)
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

        # Q2 post-implementation PMIX (validation demo)
        post_pmix_docs = []
        post_pos_total_fnb = 0.0
        for plu, name, category, daypart, complexity, price, food_cost, packaging, base_units in ITEM_CATALOG:
            bump = IMPLEMENTED_PRICE_BUMPS.get(plu, 0.0)
            realized_price = price + bump
            units = round(base_units * multiplier * SUMMER_SLOW_FACTOR * (ELASTICITY_DIP if bump else 1.0))
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

        # Labor matrix
        await db.labor_matrix.insert_many(
            [
                {
                    "_id": new_id(),
                    "tenant_id": tenant_id,
                    "location_id": location_id,
                    "daypart": "dinner",
                    "hours": round(DINNER_LABOR_HOURS_BASE * multiplier, 1),
                    "blended_rate": BLENDED_RATE,
                    "complexity_weights": {"simple": 0.7, "moderate": 1.0, "complex": 1.6},
                },
                {
                    "_id": new_id(),
                    "tenant_id": tenant_id,
                    "location_id": location_id,
                    "daypart": "all_day",
                    "hours": round(ALL_DAY_LABOR_HOURS_BASE * multiplier, 1),
                    "blended_rate": BLENDED_RATE,
                    "complexity_weights": {"simple": 0.7, "moderate": 1.0, "complex": 1.6},
                },
            ]
        )

        # Financials -- set to reconcile cleanly (small realistic noise, within tolerance)
        reported_gross_sales = round(pos_total_fnb * 1.004, 2)
        await db.financials.insert_one(
            {
                "_id": new_id(),
                "tenant_id": tenant_id,
                "location_id": location_id,
                "period_start": PERIOD_START,
                "period_end": PERIOD_END,
                "gross_sales": reported_gross_sales,
                "food_cost_actual": round(pos_total_fnb * 0.29, 2),
                "labor_cost_actual": round(
                    (DINNER_LABOR_HOURS_BASE + ALL_DAY_LABOR_HOURS_BASE) * multiplier * BLENDED_RATE, 2
                ),
            }
        )

        pos_total = compute_pos_total(pmix_docs, exclude_plus=EXCLUDED_PLUS)
        recon = reconcile(
            location_id=location_id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            pos_total=pos_total,
            reported_gross_sales=reported_gross_sales,
            tolerance_pct=2.0,
        )
        recon_doc = dict(recon)
        recon_doc["_id"] = new_id()
        recon_doc["tenant_id"] = tenant_id
        recon_doc["run_at"] = datetime.now(timezone.utc)
        await db.reconciliation_runs.insert_one(recon_doc)

        # Q2 financials + reconciliation so the validation gate is already open
        post_reported = round(post_pos_total_fnb * 1.003, 2)
        await db.financials.insert_one(
            {
                "_id": new_id(),
                "tenant_id": tenant_id,
                "location_id": location_id,
                "period_start": POST_PERIOD_START,
                "period_end": POST_PERIOD_END,
                "gross_sales": post_reported,
                "food_cost_actual": round(post_pos_total_fnb * 0.30, 2),
                "labor_cost_actual": round(
                    (DINNER_LABOR_HOURS_BASE + ALL_DAY_LABOR_HOURS_BASE)
                    * multiplier * SUMMER_SLOW_FACTOR * BLENDED_RATE, 2
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

        # Competitors
        await db.competitors.insert_many(
            [
                {
                    "_id": new_id(),
                    "tenant_id": tenant_id,
                    "location_id": location_id,
                    "competitor_name": name,
                    "item_name": item_name,
                    "price": price,
                }
                for name, item_name, price in COMPETITORS
            ]
        )

    # Generate initial pending recommendations for every location so the
    # Approval Queue has real data out of the box.
    for code, location_id in location_ids.items():
        items = await build_location_item_metrics(
            db, tenant_id=tenant_id, location_id=location_id,
            period_start=PERIOD_START, period_end=PERIOD_END,
        )
        if not items:
            continue
        location = await db.locations.find_one({"_id": location_id})
        quadrant_by_plu = {q.plu: q.quadrant for q in classify_quadrants(items)}
        revenue_baseline = sum(i.revenue for i in items)
        median_prime_cost_pct = statistics.median(i.prime_cost_pct for i in items)

        recs = generate_recommendations(
            items, quadrant_by_plu,
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
    print("Seeded Rook & Roast demo tenant.")
    print(f"  tenant_id:  {result['tenant_id']}")
    print(f"  api_token:  {result['api_token']}  (use as: Authorization: Bearer <token>)")
    print(f"  locations:  {result['location_ids']}")


if __name__ == "__main__":
    asyncio.run(_main())
