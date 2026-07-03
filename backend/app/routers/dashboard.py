from __future__ import annotations

from collections import Counter
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_tenant
from app.db import get_database
from app.services.gate import require_reconciled
from app.services.menu_engineering import classify_quadrants
from app.services.pipeline import build_location_item_metrics
from app.services.prime_cost import aggregate
from app.services.pro_forma import compute_pro_forma

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/brand")
async def brand_dashboard(period_start: datetime, period_end: datetime, tenant: dict = Depends(get_current_tenant)):
    db = get_database()
    locations = await db.locations.find({"tenant_id": tenant["_id"]}).to_list(length=None)

    total_revenue = 0.0
    total_prime_cost_dollars = 0.0
    total_cm_dollars = 0.0
    location_summaries = []

    for loc in locations:
        try:
            await require_reconciled(db, tenant_id=tenant["_id"], location_id=loc["_id"])
        except HTTPException:
            location_summaries.append(
                {"location_id": loc["_id"], "name": loc["name"], "status": "reconciliation_pending"}
            )
            continue

        items = await build_location_item_metrics(
            db, tenant_id=tenant["_id"], location_id=loc["_id"],
            period_start=period_start, period_end=period_end,
        )
        if not items:
            location_summaries.append(
                {"location_id": loc["_id"], "name": loc["name"], "status": "no_data"}
            )
            continue

        revenue = sum(i.revenue for i in items)
        prime_cost_dollars = sum(i.prime_cost * i.units_sold for i in items)
        cm_dollars = sum(i.cm_dollars * i.units_sold for i in items)

        total_revenue += revenue
        total_prime_cost_dollars += prime_cost_dollars
        total_cm_dollars += cm_dollars

        location_summaries.append(
            {
                "location_id": loc["_id"],
                "name": loc["name"],
                "status": "ok",
                "revenue": round(revenue, 2),
                "prime_cost_pct": round(prime_cost_dollars / revenue, 4) if revenue else 0.0,
                "cm_dollars": round(cm_dollars, 2),
                "item_count": len(items),
            }
        )

    recs = await db.recommendations.find({"tenant_id": tenant["_id"]}).to_list(length=None)
    pro_forma = compute_pro_forma(recs)

    projected_bps_lift = sum(
        r.get("projected_bps_lift") or 0 for r in recs if r["status"] in ("pending", "approved", "modified")
    )

    return {
        "period_start": period_start,
        "period_end": period_end,
        "combined_revenue": round(total_revenue, 2),
        "blended_prime_cost_pct": round(total_prime_cost_dollars / total_revenue, 4) if total_revenue else 0.0,
        "combined_cm_dollars": round(total_cm_dollars, 2),
        "projected_bps_lift": round(projected_bps_lift, 1),
        "approved_cash_flow_impact": pro_forma["brand_period_cash_impact"],
        "locations": location_summaries,
        "pro_forma": pro_forma,
    }


@router.get("/location/{location_id}")
async def location_dashboard(
    location_id: str, period_start: datetime, period_end: datetime, tenant: dict = Depends(get_current_tenant)
):
    db = get_database()
    location = await db.locations.find_one({"_id": location_id, "tenant_id": tenant["_id"]})
    if not location:
        raise HTTPException(404, "Location not found")

    await require_reconciled(db, tenant_id=tenant["_id"], location_id=location_id)
    items = await build_location_item_metrics(
        db, tenant_id=tenant["_id"], location_id=location_id,
        period_start=period_start, period_end=period_end,
    )
    if not items:
        raise HTTPException(404, "No PMIX-matched menu items for this location/period")

    revenue = sum(i.revenue for i in items)
    prime_cost_dollars = sum(i.prime_cost * i.units_sold for i in items)
    labor_dollars = sum(i.labor_cost * i.units_sold for i in items)

    quadrants = classify_quadrants(items)
    quadrant_counts = Counter(q.quadrant for q in quadrants)
    total_items = len(quadrants)

    return {
        "location_id": location_id,
        "name": location["name"],
        "revenue": round(revenue, 2),
        "prime_cost_pct": round(prime_cost_dollars / revenue, 4) if revenue else 0.0,
        "labor_allocation_pct": round(labor_dollars / revenue, 4) if revenue else 0.0,
        "items_analyzed": total_items,
        "quadrant_mix": {
            q: round(quadrant_counts.get(q, 0) / total_items, 4) if total_items else 0.0
            for q in ("star", "plowhorse", "puzzle", "dog")
        },
        "category_performance": aggregate(items, "category"),
    }
