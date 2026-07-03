from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import get_current_tenant
from app.db import get_database
from app.models.schemas import CompetitorEntry, LocationCreate, Season
from app.utils import new_id

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("")
async def list_locations(tenant: dict = Depends(get_current_tenant)):
    db = get_database()
    locations = await db.locations.find({"tenant_id": tenant["_id"]}).to_list(length=None)
    return locations


@router.post("")
async def create_location(payload: LocationCreate, tenant: dict = Depends(get_current_tenant)):
    db = get_database()
    doc = payload.model_dump()
    doc["tenant_id"] = tenant["_id"]
    doc["_id"] = new_id()
    doc["seasons"] = []
    await db.locations.insert_one(doc)
    return doc


@router.get("/{location_id}")
async def get_location(location_id: str, tenant: dict = Depends(get_current_tenant)):
    db = get_database()
    return await db.locations.find_one({"_id": location_id, "tenant_id": tenant["_id"]})


@router.post("/{location_id}/seasons")
async def set_seasons(location_id: str, seasons: list[Season], tenant: dict = Depends(get_current_tenant)):
    db = get_database()
    await db.locations.update_one(
        {"_id": location_id, "tenant_id": tenant["_id"]},
        {"$set": {"seasons": [s.model_dump() for s in seasons]}},
    )
    return await db.locations.find_one({"_id": location_id, "tenant_id": tenant["_id"]})


@router.post("/{location_id}/competitors")
async def add_competitor(location_id: str, payload: CompetitorEntry, tenant: dict = Depends(get_current_tenant)):
    db = get_database()
    doc = payload.model_dump()
    doc["tenant_id"] = tenant["_id"]
    doc["location_id"] = location_id
    doc["_id"] = new_id()
    await db.competitors.insert_one(doc)
    return doc


@router.get("/{location_id}/competitors")
async def list_competitors(location_id: str, tenant: dict = Depends(get_current_tenant)):
    db = get_database()
    return await db.competitors.find(
        {"tenant_id": tenant["_id"], "location_id": location_id}
    ).to_list(length=None)
