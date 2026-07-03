from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
import io

from app.auth import get_current_tenant
from app.db import get_database
from app.services.export_xlsx import build_item_analysis_workbook
from app.services.gate import require_reconciled
from app.services.menu_engineering import classify_quadrants, pareto_analysis
from app.services.pipeline import build_location_item_metrics
from app.services.prime_cost import aggregate

router = APIRouter(prefix="/items", tags=["items"])


async def _location_items(db, tenant_id: str, location_id: str, period_start: datetime, period_end: datetime):
    await require_reconciled(db, tenant_id=tenant_id, location_id=location_id)
    items = await build_location_item_metrics(
        db, tenant_id=tenant_id, location_id=location_id, period_start=period_start, period_end=period_end
    )
    if not items:
        raise HTTPException(404, "No PMIX-matched menu items found for this location/period")
    return items


@router.get("")
async def list_items(
    location_id: str,
    period_start: datetime,
    period_end: datetime,
    category: str | None = None,
    daypart: str | None = None,
    quadrant: str | None = None,
    flagged_only: bool = False,
    tenant: dict = Depends(get_current_tenant),
):
    db = get_database()
    items = await _location_items(db, tenant["_id"], location_id, period_start, period_end)
    quadrants = {q.plu: q.quadrant for q in classify_quadrants(items)}

    location = await db.locations.find_one({"_id": location_id, "tenant_id": tenant["_id"]})
    location_name = location["name"] if location else location_id

    rows = []
    for i in items:
        q = quadrants.get(i.plu, "dog")
        if category and i.category != category:
            continue
        if daypart and i.daypart != daypart:
            continue
        if quadrant and q != quadrant:
            continue
        if flagged_only and not i.is_food_cost_mirage:
            continue
        rows.append(
            {
                "plu": i.plu,
                "name": i.name,
                "category": i.category,
                "daypart": i.daypart,
                "location_id": location_id,
                "location_name": location_name,
                "units_sold": i.units_sold,
                "price": i.price,
                "food_cost": i.food_cost,
                "labor_cost": i.labor_cost,
                "packaging_cost": i.packaging_cost,
                "revenue": i.revenue,
                "prime_cost_pct": i.prime_cost_pct,
                "food_cost_pct": i.food_cost_pct,
                "cm_dollars": i.cm_dollars,
                "cm_pct": i.cm_pct,
                "quadrant": q,
                "is_food_cost_mirage": i.is_food_cost_mirage,
            }
        )
    return rows


@router.get("/aggregate")
async def item_aggregate(
    location_id: str,
    period_start: datetime,
    period_end: datetime,
    by: str = Query("category", pattern="^(category|daypart|__all__)$"),
    tenant: dict = Depends(get_current_tenant),
):
    db = get_database()
    items = await _location_items(db, tenant["_id"], location_id, period_start, period_end)
    return aggregate(items, by)


@router.get("/pareto")
async def item_pareto(
    location_id: str,
    period_start: datetime,
    period_end: datetime,
    metric: str = Query("revenue", pattern="^(revenue|cm_dollars)$"),
    tenant: dict = Depends(get_current_tenant),
):
    db = get_database()
    items = await _location_items(db, tenant["_id"], location_id, period_start, period_end)
    return pareto_analysis(items, metric=metric)


@router.get("/export.xlsx")
async def export_items_xlsx(
    location_id: str,
    period_start: datetime,
    period_end: datetime,
    tenant: dict = Depends(get_current_tenant),
):
    rows = await list_items(
        location_id=location_id, period_start=period_start, period_end=period_end,
        category=None, daypart=None, quadrant=None, flagged_only=False, tenant=tenant,
    )
    content = build_item_analysis_workbook(tenant_name=tenant["name"], items=rows)
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=margin-iq-item-analysis.xlsx"},
    )
