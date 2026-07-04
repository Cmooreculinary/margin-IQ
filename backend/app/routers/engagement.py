from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.auth import get_current_tenant
from app.db import get_database

router = APIRouter(prefix="/engagement", tags=["engagement"])


@router.get("/plan")
async def get_engagement_plan(tenant: dict = Depends(get_current_tenant)):
    db = get_database()
    plan = await db.engagement_plans.find_one({"tenant_id": tenant["_id"]})
    if not plan:
        raise HTTPException(404, "No engagement plan on file for this tenant")

    return {
        "tenant": {
            "name": tenant["name"],
            "slug": tenant["slug"],
            "monitoring_tier": tenant.get("monitoring_tier"),
        },
        "plan": plan,
    }
