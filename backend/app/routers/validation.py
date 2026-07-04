from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException

from app.auth import get_current_tenant
from app.db import get_database
from app.services.gate import require_reconciled
from app.services.pipeline import build_location_item_metrics
from app.services.validation import build_baseline_snapshot, measure_against_baseline
from app.utils import new_id

router = APIRouter(prefix="/validation", tags=["validation"])


@router.post("/baseline/lock")
async def lock_baseline(
    location_id: str,
    period_start: datetime,
    period_end: datetime,
    signed_by: str = Body(..., embed=True),
    acknowledged: bool = Body(..., embed=True),
    tenant: dict = Depends(get_current_tenant),
):
    """Lock the season-matched baseline for a location. Requires an explicit
    digital acknowledgment -- the timestamped sign-off is the contract the
    post-implementation measurement will be judged against."""
    if not acknowledged:
        raise HTTPException(400, "Baseline lock requires explicit acknowledgment (acknowledged=true)")

    db = get_database()
    await require_reconciled(db, tenant_id=tenant["_id"], location_id=location_id)

    existing = await db.baselines.find_one({"tenant_id": tenant["_id"], "location_id": location_id})
    if existing:
        raise HTTPException(
            409,
            "A locked baseline already exists for this location. Baselines are immutable "
            "by design; contact support to void one that was locked in error.",
        )

    items = await build_location_item_metrics(
        db, tenant_id=tenant["_id"], location_id=location_id,
        period_start=period_start, period_end=period_end,
    )
    if not items:
        raise HTTPException(404, "No item metrics available to lock a baseline from")

    snapshot = build_baseline_snapshot(
        items, location_id=location_id, period_start=period_start,
        period_end=period_end, signed_by=signed_by,
    )
    snapshot["_id"] = new_id()
    snapshot["tenant_id"] = tenant["_id"]
    await db.baselines.insert_one(snapshot)

    return {k: v for k, v in snapshot.items() if k != "items"} | {"item_count": len(snapshot["items"])}


@router.get("/baseline/{location_id}")
async def get_baseline(location_id: str, tenant: dict = Depends(get_current_tenant)):
    db = get_database()
    baseline = await db.baselines.find_one({"tenant_id": tenant["_id"], "location_id": location_id})
    if not baseline:
        raise HTTPException(404, "No locked baseline for this location")
    return {k: v for k, v in baseline.items() if k != "items"} | {"item_count": len(baseline["items"])}


@router.post("/measure")
async def measure(
    location_id: str,
    post_period_start: datetime,
    post_period_end: datetime,
    food_inflation_pct: float = Body(0.0, embed=True),
    seasonal_index_baseline: float = Body(1.0, embed=True),
    seasonal_index_post: float = Body(1.0, embed=True),
    tenant: dict = Depends(get_current_tenant),
):
    """Measure actual post-implementation performance against the locked
    baseline, adjusted for documented seasonality and food-cost inflation.
    Returns (and stores) the P&L bridge, validated BPS lift, and Offset %."""
    db = get_database()
    await require_reconciled(db, tenant_id=tenant["_id"], location_id=location_id)

    baseline = await db.baselines.find_one({"tenant_id": tenant["_id"], "location_id": location_id})
    if not baseline:
        raise HTTPException(409, "Lock a baseline before running a validation measurement")

    excluded = await db.menu_items.find(
        {"tenant_id": tenant["_id"], "is_excluded": True}
    ).to_list(length=None)
    excluded_plus = {i["plu"] for i in excluded}

    pmix_rows = await db.pmix_records.find(
        {
            "tenant_id": tenant["_id"],
            "location_id": location_id,
            "period_start": {"$gte": post_period_start},
            "period_end": {"$lte": post_period_end},
        }
    ).to_list(length=None)
    if not pmix_rows:
        raise HTTPException(404, "No PMIX data in the post-implementation period")

    # Aggregate to one actuals row per PLU (a period can span multiple uploads).
    actuals: dict[str, dict] = {}
    for row in pmix_rows:
        if row["plu"] in excluded_plus:
            continue
        agg = actuals.setdefault(
            row["plu"],
            {"plu": row["plu"], "item_name": row.get("item_name", row["plu"]), "units_sold": 0, "gross_revenue": 0.0},
        )
        agg["units_sold"] += row["units_sold"]
        agg["gross_revenue"] += row["gross_revenue"]

    result = measure_against_baseline(
        baseline,
        list(actuals.values()),
        seasonal_index_baseline=seasonal_index_baseline,
        seasonal_index_post=seasonal_index_post,
        food_inflation_pct=food_inflation_pct,
    )

    doc = dict(result)
    doc["_id"] = new_id()
    doc["tenant_id"] = tenant["_id"]
    doc["location_id"] = location_id
    doc["post_period_start"] = post_period_start
    doc["post_period_end"] = post_period_end
    await db.validation_runs.insert_one(doc)

    return result


@router.get("/runs")
async def list_runs(location_id: str | None = None, tenant: dict = Depends(get_current_tenant)):
    db = get_database()
    query: dict = {"tenant_id": tenant["_id"]}
    if location_id:
        query["location_id"] = location_id
    runs = await db.validation_runs.find(query).sort("measured_at", -1).to_list(length=None)
    return runs
