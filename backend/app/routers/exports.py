from __future__ import annotations

import io
from collections import Counter
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.auth import get_current_tenant
from app.db import get_database
from app.services.export_pdf import build_analysis_deck, build_recommendations_deck
from app.services.gate import require_reconciled
from app.services.menu_engineering import classify_quadrants
from app.services.pipeline import build_location_item_metrics
from app.services.pro_forma import compute_pro_forma

router = APIRouter(prefix="/exports", tags=["exports"])

PDF_MEDIA = "application/pdf"


def _period_label(period_start: datetime, period_end: datetime) -> str:
    return f"{period_start.strftime('%b %d, %Y')} – {period_end.strftime('%b %d, %Y')}"


@router.get("/analysis-deck.pdf")
async def analysis_deck(
    period_start: datetime,
    period_end: datetime,
    tenant: dict = Depends(get_current_tenant),
):
    db = get_database()
    locations = await db.locations.find({"tenant_id": tenant["_id"]}).to_list(length=None)

    total_revenue = 0.0
    total_prime = 0.0
    total_cm = 0.0
    sections = []

    for loc in locations:
        try:
            await require_reconciled(db, tenant_id=tenant["_id"], location_id=loc["_id"])
        except HTTPException:
            continue
        items = await build_location_item_metrics(
            db, tenant_id=tenant["_id"], location_id=loc["_id"],
            period_start=period_start, period_end=period_end,
        )
        if not items:
            continue

        revenue = sum(i.revenue for i in items)
        prime = sum(i.prime_cost * i.units_sold for i in items)
        cm = sum(i.cm_dollars * i.units_sold for i in items)
        total_revenue += revenue
        total_prime += prime
        total_cm += cm

        quadrants = classify_quadrants(items)
        quadrant_by_plu = {q.plu: q.quadrant for q in quadrants}
        top_items = sorted(items, key=lambda i: i.cm_dollars * i.units_sold, reverse=True)[:5]

        sections.append(
            {
                "name": loc["name"],
                "kpis": {
                    "revenue": revenue,
                    "prime_cost_pct": prime / revenue if revenue else 0.0,
                    "cm_dollars": cm,
                    "item_count": len(items),
                },
                "quadrant_counts": dict(Counter(q.quadrant for q in quadrants)),
                "top_items": [
                    {
                        "name": i.name,
                        "cm_dollars_total": i.cm_dollars * i.units_sold,
                        "quadrant": quadrant_by_plu.get(i.plu, "dog"),
                    }
                    for i in top_items
                ],
                "mirage_items": [
                    {
                        "name": i.name,
                        "food_margin_pct": 1 - i.food_cost_pct,
                        "prime_margin_pct": 1 - i.prime_cost_pct,
                    }
                    for i in items
                    if i.is_food_cost_mirage
                ],
            }
        )

    if not sections:
        raise HTTPException(409, "No reconciled locations with data in this period")

    content = build_analysis_deck(
        tenant_name=tenant["name"],
        period_label=_period_label(period_start, period_end),
        brand_kpis={
            "combined_revenue": total_revenue,
            "blended_prime_cost_pct": total_prime / total_revenue if total_revenue else 0.0,
            "combined_cm_dollars": total_cm,
            "location_count": len(sections),
        },
        location_sections=sections,
    )
    return StreamingResponse(
        io.BytesIO(content), media_type=PDF_MEDIA,
        headers={"Content-Disposition": "attachment; filename=margin-iq-analysis-deck.pdf"},
    )


@router.get("/recommendations-deck.pdf")
async def recommendations_deck(
    period_start: datetime,
    period_end: datetime,
    tenant: dict = Depends(get_current_tenant),
):
    db = get_database()
    recs = await db.recommendations.find({"tenant_id": tenant["_id"]}).to_list(length=None)
    if not recs:
        raise HTTPException(404, "No recommendations to export")

    recs_by_location: dict[str, list[dict]] = {}
    for rec in sorted(recs, key=lambda r: (r["location_name"], r["name"])):
        recs_by_location.setdefault(rec["location_name"], []).append(rec)

    content = build_recommendations_deck(
        tenant_name=tenant["name"],
        period_label=_period_label(period_start, period_end),
        pro_forma=compute_pro_forma(recs),
        recs_by_location=recs_by_location,
    )
    return StreamingResponse(
        io.BytesIO(content), media_type=PDF_MEDIA,
        headers={"Content-Disposition": "attachment; filename=margin-iq-recommendations-deck.pdf"},
    )
