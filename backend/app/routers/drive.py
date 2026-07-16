"""Google Drive integration endpoints: OAuth connect/callback, file browsing,
and import-to-scan pipeline that feeds Drive files through Claude extraction."""
from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from app.auth import get_current_tenant
from app.db import get_database
from app.services import document_scan, google_drive
from app.utils import new_id

router = APIRouter(prefix="/drive", tags=["drive"])


# --- OAuth flow ---


@router.get("/connect")
async def connect_drive(tenant: dict = Depends(get_current_tenant)):
    url = google_drive.build_auth_url(tenant["_id"])
    return {"auth_url": url}


@router.get("/callback")
async def drive_callback(code: str = Query(...), state: str = Query(...)):
    """Google redirects here after consent. State carries the tenant_id."""
    tokens = await google_drive.exchange_code(code)
    db = get_database()
    await db.drive_credentials.update_one(
        {"tenant_id": state},
        {
            "$set": {
                "tenant_id": state,
                "access_token": tokens.get("access_token", ""),
                "refresh_token": tokens.get("refresh_token", ""),
                "token_type": tokens.get("token_type", ""),
                "scope": tokens.get("scope", ""),
            }
        },
        upsert=True,
    )
    return RedirectResponse("/drive-import?connected=1")


@router.get("/status")
async def drive_status(tenant: dict = Depends(get_current_tenant)):
    db = get_database()
    creds = await db.drive_credentials.find_one({"tenant_id": tenant["_id"]})
    return {"connected": creds is not None}


@router.delete("/disconnect")
async def disconnect_drive(tenant: dict = Depends(get_current_tenant)):
    db = get_database()
    await db.drive_credentials.delete_one({"tenant_id": tenant["_id"]})
    return {"disconnected": True}


# --- File browsing ---


@router.get("/files")
async def list_drive_files(
    folder_id: str | None = Query(None),
    page_token: str | None = Query(None),
    tenant: dict = Depends(get_current_tenant),
):
    db = get_database()
    result = await google_drive.list_files(db, tenant["_id"], folder_id, page_token)
    files = []
    for f in result.get("files", []):
        mime = f.get("mimeType", "")
        is_folder = mime == "application/vnd.google-apps.folder"
        importable = mime in google_drive.IMPORTABLE_MIMES or mime == "application/vnd.google-apps.spreadsheet"
        files.append(
            {
                "id": f["id"],
                "name": f["name"],
                "mimeType": mime,
                "size": f.get("size"),
                "modifiedTime": f.get("modifiedTime"),
                "isFolder": is_folder,
                "importable": importable or is_folder,
            }
        )
    return {
        "files": files,
        "nextPageToken": result.get("nextPageToken"),
    }


@router.get("/search")
async def search_drive_files(
    q: str = Query(..., min_length=1),
    tenant: dict = Depends(get_current_tenant),
):
    db = get_database()
    result = await google_drive.search_files(db, tenant["_id"], q)
    files = []
    for f in result.get("files", []):
        mime = f.get("mimeType", "")
        is_folder = mime == "application/vnd.google-apps.folder"
        importable = mime in google_drive.IMPORTABLE_MIMES or mime == "application/vnd.google-apps.spreadsheet"
        files.append(
            {
                "id": f["id"],
                "name": f["name"],
                "mimeType": mime,
                "size": f.get("size"),
                "modifiedTime": f.get("modifiedTime"),
                "isFolder": is_folder,
                "importable": importable or is_folder,
            }
        )
    return {"files": files}


# --- Import (download + scan) ---


class ImportRequest(BaseModel):
    file_id: str
    file_name: str


class BatchImportRequest(BaseModel):
    files: list[ImportRequest]


@router.post("/import")
async def import_file(req: ImportRequest, tenant: dict = Depends(get_current_tenant)):
    """Download a single file from Drive and run it through Claude extraction."""
    db = get_database()
    raw, mime_type, filename = await google_drive.download_file(db, tenant["_id"], req.file_id)

    if not raw:
        raise HTTPException(400, "Downloaded file is empty.")

    scan_mime = _to_scan_mime(mime_type, filename)
    data_b64 = base64.standard_b64encode(raw).decode()

    result = await document_scan.extract_document(data_b64, scan_mime, filename)
    result["filename"] = filename
    result["source"] = "google_drive"
    result["drive_file_id"] = req.file_id
    return result


@router.post("/import/batch")
async def import_batch(req: BatchImportRequest, tenant: dict = Depends(get_current_tenant)):
    """Download and scan multiple Drive files. Returns results per file."""
    db = get_database()
    results = []
    for f in req.files:
        try:
            raw, mime_type, filename = await google_drive.download_file(
                db, tenant["_id"], f.file_id
            )
            if not raw:
                results.append({"filename": f.file_name, "error": "File is empty"})
                continue
            scan_mime = _to_scan_mime(mime_type, filename)
            data_b64 = base64.standard_b64encode(raw).decode()
            result = await document_scan.extract_document(data_b64, scan_mime, filename)
            result["filename"] = filename
            result["source"] = "google_drive"
            result["drive_file_id"] = f.file_id
            results.append(result)
        except HTTPException as exc:
            results.append({"filename": f.file_name, "error": exc.detail})
        except Exception as exc:
            results.append({"filename": f.file_name, "error": str(exc)})
    return {"results": results}


def _to_scan_mime(mime_type: str, filename: str) -> str:
    """Map download MIME types to the types the scan service accepts."""
    if mime_type in document_scan.IMAGE_MEDIA_TYPES:
        return mime_type
    if mime_type == document_scan.PDF_MEDIA_TYPE:
        return mime_type
    # Excel files (.xlsx, .xls, .xlsm) -- the scan service can't process
    # spreadsheets directly, but we can treat them as PDFs won't work either.
    # For spreadsheets, we need to explain the limitation.
    excel_mimes = {
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
        "application/vnd.ms-excel.sheet.macroEnabled.12",
    }
    if mime_type in excel_mimes:
        raise HTTPException(
            415,
            f"Spreadsheet files ({filename}) cannot be processed by AI document "
            "scanning directly. Export it as PDF first, or upload the PDF version "
            "from your Drive folder.",
        )
    raise HTTPException(415, f"File type '{mime_type}' is not supported for import.")
