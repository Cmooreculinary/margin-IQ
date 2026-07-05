"""Glue layer: pulls a location's menu items + PMIX + labor matrix out of the
database and turns them into the ItemPrimeCost objects every downstream service
(menu engineering, recommendations, dashboard, exports) operates on."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from app.services.labor_allocation import allocate_labor_cost_per_item
from app.services.prime_cost import ItemPrimeCost, compute_prime_cost


async def build_location_item_metrics(
    db,
    *,
    tenant_id: str,
    location_id: str,
    period_start: datetime,
    period_end: datetime,
) -> list[ItemPrimeCost]:
    menu_items = await db.menu_items.find(
        {
            "tenant_id": tenant_id,
            "is_excluded": {"$ne": True},
            "$or": [{"location_id": location_id}, {"location_id": None}],
        }
    ).to_list(length=None)

    if not menu_items:
        return []

    plus = [i["plu"] for i in menu_items]
    pmix_cursor = db.pmix_records.find(
        {
            "tenant_id": tenant_id,
            "location_id": location_id,
            "plu": {"$in": plus},
            "period_start": {"$gte": period_start},
            "period_end": {"$lte": period_end},
        }
    )
    pmix_rows = await pmix_cursor.to_list(length=None)

    units_by_plu: dict[str, int] = defaultdict(int)
    for row in pmix_rows:
        units_by_plu[row["plu"]] += row["units_sold"]

    labor_matrix = await db.labor_matrix.find(
        {"tenant_id": tenant_id, "location_id": location_id}
    ).to_list(length=None)

    labor_input = [
        {
            "plu": mi["plu"],
            "daypart": mi["daypart"],
            "prep_complexity": mi["prep_complexity"],
            "units_sold": units_by_plu.get(mi["plu"], 0),
        }
        for mi in menu_items
    ]
    labor_per_unit = allocate_labor_cost_per_item(items=labor_input, labor_matrix=labor_matrix)

    results = []
    for mi in menu_items:
        units_sold = units_by_plu.get(mi["plu"], 0)
        if units_sold == 0:
            continue
        results.append(
            compute_prime_cost(
                plu=mi["plu"],
                name=mi["name"],
                category=mi["category"],
                daypart=mi["daypart"],
                price=mi["price"],
                food_cost=mi["recipe_food_cost"],
                labor_cost=labor_per_unit.get(mi["plu"], 0.0),
                packaging_cost=mi.get("packaging_cost", 0.0),
                units_sold=units_sold,
            )
        )
    return results
