from __future__ import annotations

import io
from datetime import datetime

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.adapters.toast import ToastAdapter
from app.auth import get_current_tenant
from app.config import settings
from app.db import get_database
from app.models.schemas import FinancialsUpload, LaborMatrixEntry, MenuItemCreate
from app.services.reconciliation import compute_pos_total, reconcile
from app.utils import new_id

router = APIRouter(prefix="/ingestion", tags=["ingestion"])

_ADAPTERS = {"toast": ToastAdapter()}


@router.post("/pmix")
async def upload_pmix(
    location_id: str = Form(...),
    period_start: datetime = Form(...),
    period_end: datetime = Form(...),
    pos: str = Form(default="toast"),
    file: UploadFile = File(...),
    tenant: dict = Depends(get_current_tenant),
):
    adapter = _ADAPTERS.get(pos)
    if not adapter:
        raise HTTPException(400, f"No adapter registered for POS '{pos}'. Supported: {list(_ADAPTERS)}")

    raw = await file.read()
    buf = io.BytesIO(raw)
    buf.name = file.filename or ""
    rows = adapter.parse_pmix(buf, location_id, period_start=period_start, period_end=period_end)

    db = get_database()
    for row in rows:
        row["tenant_id"] = tenant["_id"]
        row["_id"] = new_id()
    if rows:
        await db.pmix_records.insert_many(rows)

    return {"location_id": location_id, "rows_ingested": len(rows), "source": pos}


@router.post("/financials")
async def upload_financials(payload: FinancialsUpload, tenant: dict = Depends(get_current_tenant)):
    db = get_database()
    doc = payload.model_dump()
    doc["tenant_id"] = tenant["_id"]
    doc["_id"] = new_id()
    await db.financials.insert_one(doc)
    return doc


@router.post("/labor-matrix")
async def upsert_labor_matrix(payload: LaborMatrixEntry, tenant: dict = Depends(get_current_tenant)):
    db = get_database()
    doc = payload.model_dump()
    doc["tenant_id"] = tenant["_id"]
    await db.labor_matrix.update_one(
        {"tenant_id": tenant["_id"], "location_id": doc["location_id"], "daypart": doc["daypart"]},
        {"$set": doc},
        upsert=True,
    )
    return doc


@router.post("/menu-items")
async def create_menu_item(payload: MenuItemCreate, tenant: dict = Depends(get_current_tenant)):
    db = get_database()
    doc = payload.model_dump()
    doc["tenant_id"] = tenant["_id"]
    doc["_id"] = new_id()
    await db.menu_items.insert_one(doc)
    return doc


@router.post("/menu-items/{plu}/exclude")
async def set_plu_exclusion(
    plu: str,
    excluded: bool,
    location_id: str | None = None,
    tenant: dict = Depends(get_current_tenant),
):
    """Tag a non-F&B PLU (cover fee, retail, merch) so it's excluded from prime
    cost math. It still shows up in the raw revenue view -- just not here."""
    db = get_database()
    query: dict = {"tenant_id": tenant["_id"], "plu": plu}
    if location_id:
        query["location_id"] = location_id
    result = await db.menu_items.update_many(query, {"$set": {"is_excluded": excluded}})
    return {"plu": plu, "excluded": excluded, "matched": result.matched_count}


@router.post("/reconcile")
async def run_reconciliation(
    location_id: str,
    period_start: datetime,
    period_end: datetime,
    tolerance_pct: float | None = None,
    tenant: dict = Depends(get_current_tenant),
):
    db = get_database()
    excluded_items = await db.menu_items.find(
        {"tenant_id": tenant["_id"], "location_id": location_id, "is_excluded": True}
    ).to_list(length=None)
    excluded_plus = {i["plu"] for i in excluded_items}

    pmix_rows = await db.pmix_records.find(
        {
            "tenant_id": tenant["_id"],
            "location_id": location_id,
            "period_start": {"$gte": period_start},
            "period_end": {"$lte": period_end},
        }
    ).to_list(length=None)

    financials = await db.financials.find_one(
        {
            "tenant_id": tenant["_id"],
            "location_id": location_id,
            "period_start": period_start,
            "period_end": period_end,
        }
    )
    if not financials:
        raise HTTPException(404, "No reported financials on file for this location/period")

    pos_total = compute_pos_total(pmix_rows, exclude_plus=excluded_plus)
    result = reconcile(
        location_id=location_id,
        period_start=period_start,
        period_end=period_end,
        pos_total=pos_total,
        reported_gross_sales=financials["gross_sales"],
        tolerance_pct=tolerance_pct or settings.default_reconciliation_tolerance_pct,
    )

    doc = dict(result)
    doc["tenant_id"] = tenant["_id"]
    doc["_id"] = new_id()
    doc["run_at"] = datetime.utcnow()
    await db.reconciliation_runs.insert_one(doc)
    return result


@router.get("/reconciliation-status/{location_id}")
async def reconciliation_status(location_id: str, tenant: dict = Depends(get_current_tenant)):
    db = get_database()
    latest = await db.reconciliation_runs.find(
        {"tenant_id": tenant["_id"], "location_id": location_id}
    ).sort("run_at", -1).to_list(length=1)
    if not latest:
        return {"status": "no_reconciliation_run", "passed": False}
    return latest[0]
