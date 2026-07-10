"""Google Drive integration: OAuth2 flow and file operations.

Lets operators connect their Google Drive, browse shared folders, and pull
distributor files (invoices, order guides, price comparisons) into the
document scanning pipeline for automatic extraction.
"""
from __future__ import annotations

import urllib.parse
from typing import Any

import httpx
from fastapi import HTTPException

from app.config import settings

SCOPES = "https://www.googleapis.com/auth/drive.readonly"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
DRIVE_API = "https://www.googleapis.com/drive/v3"

IMPORTABLE_MIMES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/vnd.ms-excel.sheet.macroEnabled.12",
}

MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024


def _require_configured() -> None:
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(
            503,
            "Google Drive is not configured: set GOOGLE_CLIENT_ID and "
            "GOOGLE_CLIENT_SECRET environment variables on the server.",
        )


def build_auth_url(tenant_id: str) -> str:
    _require_configured()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "state": tenant_id,
    }
    return f"{AUTH_URL}?{urllib.parse.urlencode(params)}"


async def exchange_code(code: str) -> dict[str, Any]:
    _require_configured()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code",
            },
        )
    if resp.status_code != 200:
        raise HTTPException(502, f"Google token exchange failed: {resp.text}")
    return resp.json()


async def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    _require_configured()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "grant_type": "refresh_token",
            },
        )
    if resp.status_code != 200:
        raise HTTPException(502, f"Google token refresh failed: {resp.text}")
    return resp.json()


async def _get_access_token(db: Any, tenant_id: str) -> str:
    creds = await db.drive_credentials.find_one({"tenant_id": tenant_id})
    if not creds:
        raise HTTPException(401, "Google Drive is not connected. Please connect first.")
    access_token = creds.get("access_token", "")
    refresh_token = creds.get("refresh_token")
    if not refresh_token:
        raise HTTPException(401, "Google Drive refresh token missing. Please reconnect.")
    tokens = await refresh_access_token(refresh_token)
    new_access = tokens["access_token"]
    await db.drive_credentials.update_one(
        {"tenant_id": tenant_id},
        {"$set": {"access_token": new_access}},
    )
    return new_access


async def list_files(
    db: Any,
    tenant_id: str,
    folder_id: str | None = None,
    page_token: str | None = None,
) -> dict:
    access_token = await _get_access_token(db, tenant_id)
    query_parts = ["trashed = false"]
    if folder_id:
        query_parts.append(f"'{folder_id}' in parents")

    params: dict[str, str] = {
        "q": " and ".join(query_parts),
        "fields": "nextPageToken,files(id,name,mimeType,size,modifiedTime,parents,iconLink,thumbnailLink)",
        "pageSize": "50",
        "orderBy": "folder,name",
        "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true",
    }
    if page_token:
        params["pageToken"] = page_token

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{DRIVE_API}/files",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if resp.status_code == 401:
        raise HTTPException(401, "Google Drive session expired. Please reconnect.")
    if resp.status_code != 200:
        raise HTTPException(502, f"Google Drive API error: {resp.text}")
    return resp.json()


async def search_files(
    db: Any,
    tenant_id: str,
    query: str,
) -> dict:
    access_token = await _get_access_token(db, tenant_id)
    q = f"name contains '{query}' and trashed = false"
    params: dict[str, str] = {
        "q": q,
        "fields": "files(id,name,mimeType,size,modifiedTime,parents)",
        "pageSize": "30",
        "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{DRIVE_API}/files",
            params=params,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if resp.status_code != 200:
        raise HTTPException(502, f"Google Drive search error: {resp.text}")
    return resp.json()


async def download_file(db: Any, tenant_id: str, file_id: str) -> tuple[bytes, str, str]:
    """Download a file from Drive. Returns (bytes, mime_type, filename)."""
    access_token = await _get_access_token(db, tenant_id)
    headers = {"Authorization": f"Bearer {access_token}"}

    async with httpx.AsyncClient() as client:
        meta_resp = await client.get(
            f"{DRIVE_API}/files/{file_id}",
            params={"fields": "name,mimeType,size", "supportsAllDrives": "true"},
            headers=headers,
        )
    if meta_resp.status_code != 200:
        raise HTTPException(502, f"Could not read file metadata: {meta_resp.text}")
    meta = meta_resp.json()
    filename = meta.get("name", "download")
    mime_type = meta.get("mimeType", "application/octet-stream")
    file_size = int(meta.get("size", 0))

    if file_size > MAX_DOWNLOAD_BYTES:
        raise HTTPException(413, f"File is too large ({file_size} bytes); limit is 20 MB.")

    # Google Workspace files (Sheets, Docs) need export; native files use direct download.
    is_google_type = mime_type.startswith("application/vnd.google-apps.")
    if is_google_type:
        if mime_type == "application/vnd.google-apps.spreadsheet":
            export_mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            url = f"{DRIVE_API}/files/{file_id}/export"
            params = {"mimeType": export_mime}
            mime_type = export_mime
            filename = filename + ".xlsx" if not filename.endswith(".xlsx") else filename
        else:
            raise HTTPException(
                415,
                f"Cannot import Google {mime_type.split('.')[-1]} files. "
                "Export it as PDF or XLSX first.",
            )
    else:
        url = f"{DRIVE_API}/files/{file_id}"
        params = {"alt": "media", "supportsAllDrives": "true"}

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, headers=headers, timeout=60)
    if resp.status_code != 200:
        raise HTTPException(502, f"File download failed: {resp.status_code}")

    return resp.content, mime_type, filename
