from __future__ import annotations

from fastapi import APIRouter, Depends

from app.auth import get_current_tenant
from app.products import product_manifest

router = APIRouter(prefix="/products", tags=["products"])


@router.get("")
async def products(tenant: dict = Depends(get_current_tenant)):
    return product_manifest(tenant)
