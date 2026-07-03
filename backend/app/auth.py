"""Tenant-scoped bearer auth. Every authenticated route resolves to exactly one
tenant; every DB query downstream must filter on that tenant_id. There is no
code path that reads across tenants -- hard isolation, not a soft convention."""
from __future__ import annotations

from fastapi import Header, HTTPException, status

from app.db import get_database


async def get_current_tenant(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header. Expected: Bearer <tenant_token>",
        )
    token = authorization.split(" ", 1)[1].strip()
    db = get_database()
    tenant = await db.tenants.find_one({"api_token": token})
    if not tenant:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid tenant token")
    tenant["_id"] = str(tenant["_id"])
    return tenant
