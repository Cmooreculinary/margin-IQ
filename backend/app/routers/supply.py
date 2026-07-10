from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.auth import get_current_tenant
from app.db import get_database

router = APIRouter(prefix="/supply", tags=["supply"])

# Confidence tiers worth acting on without a manual spot-check.
TRUSTED_CONFIDENCE = {"High", "Review"}


@router.get("/comparisons")
async def list_comparisons(
    cheaper_supplier: str | None = Query(default=None),
    trusted_only: bool = Query(default=False),
    tenant: dict = Depends(get_current_tenant),
):
    db = get_database()
    query: dict = {"tenant_id": tenant["_id"]}
    if cheaper_supplier:
        query["cheaper_supplier"] = cheaper_supplier
    if trusted_only:
        query["match_confidence"] = {"$in": list(TRUSTED_CONFIDENCE)}
    rows = await db.supplier_price_comparisons.find(query).sort("line", 1).to_list(length=None)
    return rows


@router.get("/catalog")
async def list_catalog(
    supplier: str | None = Query(default=None),
    category: str | None = Query(default=None),
    tenant: dict = Depends(get_current_tenant),
):
    """Standalone single-vendor price catalog -- for suppliers like Shoreline
    whose product mix (disposables, syrups, coffee-bar supplies) doesn't
    overlap with the US Foods / Shamrock food comparison, so there is nothing
    valid to diff against. Reference pricing only, no cheaper-supplier call."""
    db = get_database()
    query: dict = {"tenant_id": tenant["_id"]}
    if supplier:
        query["supplier"] = supplier
    if category:
        query["category"] = category
    rows = await db.supplier_catalog_items.find(query).sort("category", 1).to_list(length=None)
    return rows


@router.get("/summary")
async def summary(tenant: dict = Depends(get_current_tenant)):
    db = get_database()
    rows = await db.supplier_price_comparisons.find({"tenant_id": tenant["_id"]}).to_list(length=None)

    total = len(rows)
    trusted = [r for r in rows if r.get("match_confidence") in TRUSTED_CONFIDENCE and r.get("diff_pct") is not None]
    by_cheaper = {"US Foods": 0, "Shamrock": 0, "Tie": 0, "Need review": 0}
    for r in trusted:
        by_cheaper[r.get("cheaper_supplier", "Need review")] = by_cheaper.get(r.get("cheaper_supplier", "Need review"), 0) + 1

    # Illustrative switching-savings if every trusted Shamrock-cheaper line moved
    # from US Foods to Shamrock, priced per the guide's own order quantity unit.
    switchable_savings = round(
        sum(
            -r["diff_dollar_per_unit"] * r["us_qty_in_unit"]
            for r in trusted
            if r.get("cheaper_supplier") == "Shamrock" and r.get("diff_dollar_per_unit") is not None and r.get("us_qty_in_unit")
        ),
        2,
    )

    return {
        "total_items": total,
        "trusted_comparisons": len(trusted),
        "needs_review": total - len(trusted),
        "by_cheaper_supplier": by_cheaper,
        "illustrative_switching_savings": switchable_savings,
    }
