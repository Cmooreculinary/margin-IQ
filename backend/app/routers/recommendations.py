from __future__ import annotations

import io
import statistics
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.auth import get_current_tenant
from app.db import get_database
from app.models.schemas import RecommendationDecision
from app.services.export_xlsx import build_implementation_checklist_workbook
from app.services.gate import require_reconciled
from app.services.menu_engineering import classify_quadrants
from app.services.pipeline import build_location_item_metrics
from app.services.pro_forma import compute_pro_forma
from app.services.recommendations import (
    DEFAULT_ELASTICITY_BY_QUADRANT,
    generate_recommendations,
    simulate_price_change,
)
from app.utils import new_id

router = APIRouter(prefix="/recommendations", tags=["recommendations"])


@router.post("/generate")
async def generate_for_location(
    location_id: str,
    period_start: datetime,
    period_end: datetime,
    tenant: dict = Depends(get_current_tenant),
):
    db = get_database()
    await require_reconciled(db, tenant_id=tenant["_id"], location_id=location_id)

    items = await build_location_item_metrics(
        db, tenant_id=tenant["_id"], location_id=location_id,
        period_start=period_start, period_end=period_end,
    )
    if not items:
        raise HTTPException(404, "No items to generate recommendations for")

    location = await db.locations.find_one({"_id": location_id, "tenant_id": tenant["_id"]})
    location_name = location["name"] if location else location_id

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
        doc["tenant_id"] = tenant["_id"]
        doc["location_id"] = location_id
        doc["location_name"] = location_name
        doc["status"] = "pending"
        doc["created_at"] = datetime.now(timezone.utc)
        doc["decided_by"] = None
        doc["decided_at"] = None
        doc["final_price"] = None
        # carried so a later /decide with a modified price can recompute the ticker
        doc["_prime_cost"] = item.prime_cost
        doc["_units_sold"] = item.units_sold
        doc["_elasticity"] = DEFAULT_ELASTICITY_BY_QUADRANT.get(rec["quadrant"], -0.6)
        doc["_location_revenue_baseline"] = revenue_baseline
        docs.append(doc)

    # Replace any still-pending recs for this location so re-generation doesn't duplicate the queue.
    await db.recommendations.delete_many(
        {"tenant_id": tenant["_id"], "location_id": location_id, "status": "pending"}
    )
    if docs:
        await db.recommendations.insert_many(docs)

    return {"location_id": location_id, "recommendations_generated": len(docs)}


_INTERNAL_ONLY_KEYS = {"_prime_cost", "_units_sold", "_elasticity", "_location_revenue_baseline"}


def _public(rec: dict) -> dict:
    return {k: v for k, v in rec.items() if k not in _INTERNAL_ONLY_KEYS}


@router.get("")
async def list_recommendations(
    location_id: str | None = None,
    status: str | None = None,
    tenant: dict = Depends(get_current_tenant),
):
    db = get_database()
    query: dict = {"tenant_id": tenant["_id"]}
    if location_id:
        query["location_id"] = location_id
    if status:
        query["status"] = status
    recs = await db.recommendations.find(query).sort("created_at", -1).to_list(length=None)
    return [_public(r) for r in recs]


@router.post("/{rec_id}/decide")
async def decide_recommendation(
    rec_id: str, decision: RecommendationDecision, tenant: dict = Depends(get_current_tenant)
):
    db = get_database()
    rec = await db.recommendations.find_one({"_id": rec_id, "tenant_id": tenant["_id"]})
    if not rec:
        raise HTTPException(404, "Recommendation not found")

    update: dict = {
        "status": decision.status.value,
        "decided_by": decision.decided_by,
        "decided_at": datetime.now(timezone.utc),
        "decision_note": decision.note,
    }

    if decision.status.value in ("approved", "modified") and rec.get("type") == "price":
        final_price = decision.final_price if decision.final_price is not None else rec["recommended_price"]
        update["final_price"] = final_price

        if final_price != rec["current_price"] and rec.get("_prime_cost") is not None:
            sim = simulate_price_change(
                current_price=rec["current_price"],
                prime_cost=rec["_prime_cost"],
                units_sold=rec["_units_sold"],
                new_price=final_price,
                elasticity=rec["_elasticity"],
                location_revenue_baseline=rec["_location_revenue_baseline"],
            )
            update["projected_bps_lift"] = sim.projected_bps_lift
            update["pmix_offset_pct"] = sim.pmix_offset_pct
            update["projected_cash_lift"] = sim.cm_dollars_lift

    await db.recommendations.update_one({"_id": rec_id}, {"$set": update})

    await db.approval_log.insert_one(
        {
            "_id": new_id(),
            "tenant_id": tenant["_id"],
            "recommendation_id": rec_id,
            "action": decision.status.value,
            "decided_by": decision.decided_by,
            "original_recommended_price": rec.get("recommended_price"),
            "final_price": update.get("final_price"),
            "note": decision.note,
            "timestamp": datetime.now(timezone.utc),
        }
    )

    updated = await db.recommendations.find_one({"_id": rec_id})
    return _public(updated)


@router.get("/pro-forma")
async def pro_forma(
    location_id: str | None = None,
    period_days: int = 90,
    tenant: dict = Depends(get_current_tenant),
):
    db = get_database()
    query: dict = {"tenant_id": tenant["_id"]}
    if location_id:
        query["location_id"] = location_id
    recs = await db.recommendations.find(query).to_list(length=None)
    return compute_pro_forma(recs, period_days=period_days)


@router.get("/export-checklist.xlsx")
async def export_checklist(tenant: dict = Depends(get_current_tenant)):
    db = get_database()
    recs = await db.recommendations.find(
        {"tenant_id": tenant["_id"], "status": {"$in": ["approved", "modified"]}}
    ).to_list(length=None)
    content = build_implementation_checklist_workbook(
        tenant_name=tenant["name"], approved_recs=[_public(r) for r in recs]
    )
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=margin-iq-implementation-checklist.xlsx"},
    )
