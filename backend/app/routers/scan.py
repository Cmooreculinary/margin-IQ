"""Document scan ingestion: upload an image/PDF, Claude extracts the data,
the operator reviews it in the portal, then commits it to the right
collections. Nothing is written until the explicit commit call -- consistent
with the platform guardrail that no data enters analysis silently."""
from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import ValidationError

from app.auth import get_current_tenant
from app.db import get_database
from app.models.schemas import (
    CompetitorEntry,
    FinancialsUpload,
    LaborMatrixEntry,
    MenuItemCreate,
    PmixRow,
    ScanCommit,
)
from app.services import document_scan
from app.utils import new_id

router = APIRouter(prefix="/ingestion/scan", tags=["ingestion"])


@router.post("")
async def scan_document(file: UploadFile = File(...), tenant: dict = Depends(get_current_tenant)):
    media_type = (file.content_type or "").lower()
    supported = document_scan.IMAGE_MEDIA_TYPES | {document_scan.PDF_MEDIA_TYPE}
    if media_type not in supported:
        raise HTTPException(
            415,
            f"Unsupported file type '{media_type}'. Upload a photo/screenshot "
            "(PNG, JPEG, GIF, WebP) or a PDF.",
        )
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "The uploaded file is empty.")
    if len(raw) > document_scan.MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is too large; the limit is 20 MB.")

    result = await document_scan.extract_document(
        base64.standard_b64encode(raw).decode(), media_type, file.filename or "upload"
    )
    result["filename"] = file.filename
    return result


# Maps each record target to (validation model, collection name). The payload
# is validated against the same schema the manual ingestion endpoints use, so
# scanned data can never be shaped differently from hand-entered data.
_TARGETS = {
    "financials": (FinancialsUpload, "financials"),
    "menu_item": (MenuItemCreate, "menu_items"),
    "pmix_row": (PmixRow, "pmix_records"),
    "competitor": (CompetitorEntry, "competitors"),
}


@router.post("/commit")
async def commit_scan(payload: ScanCommit, tenant: dict = Depends(get_current_tenant)):
    """Write reviewed records. Each record was checked/edited by the operator
    in the portal; anything that fails schema validation rejects the whole
    commit so a partial import never happens silently."""
    db = get_database()

    validated: list[tuple[str, dict]] = []
    errors: list[str] = []
    for idx, record in enumerate(payload.records):
        data = {**record.data, "tenant_id": tenant["_id"]}
        if record.target == "labor_matrix":
            model = LaborMatrixEntry
        elif record.target in _TARGETS:
            model = _TARGETS[record.target][0]
        else:
            errors.append(f"record {idx}: unknown target '{record.target}'")
            continue
        # pmix rows don't carry tenant_id in their schema
        fields = model.model_fields
        data = {k: v for k, v in data.items() if k in fields}
        try:
            validated.append((record.target, model(**data).model_dump()))
        except ValidationError as exc:
            problems = "; ".join(f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors())
            errors.append(f"record {idx} ({record.target}): {problems}")

    if errors:
        raise HTTPException(422, {"message": "Some records are invalid; nothing was committed.", "errors": errors})

    counts: dict[str, int] = {}
    for target, doc in validated:
        if target == "labor_matrix":
            await db.labor_matrix.update_one(
                {"tenant_id": tenant["_id"], "location_id": doc["location_id"], "daypart": doc["daypart"]},
                {"$set": doc},
                upsert=True,
            )
        else:
            _, collection = _TARGETS[target]
            doc["tenant_id"] = tenant["_id"]
            doc["_id"] = new_id()
            await db[collection].insert_one(doc)
        counts[target] = counts.get(target, 0) + 1

    return {"committed": counts, "total": len(validated)}
