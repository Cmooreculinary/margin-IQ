from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.products import MARGIN_IQ, SUPPLY_AGENT, deployment_products, require_product
from app.routers import (
    dashboard,
    engagement,
    exports,
    ingestion,
    items,
    locations,
    products,
    recommendations,
    scan,
    supply,
    validation,
)

# Built frontend (copied in by the production Docker image). When present, this
# app serves the SPA too, so API + portal run as a single same-origin service.
STATIC_DIR = Path(os.environ.get("STATIC_DIR", "static"))
ENABLED_PRODUCTS = deployment_products()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.seed_demo:
        from app.db import get_database, verify_database_connection
        from app.seed.snakes_and_lattes import seed

        await verify_database_connection()
        db = get_database()
        result = await seed(db)
        tenant_id = result["tenant_id"]

        # Demo access intentionally includes both commercial products. A
        # standalone deployment still clamps access through PRODUCT_MODE.
        await db.tenants.update_one(
            {"_id": tenant_id},
            {"$set": {"products": [MARGIN_IQ, SUPPLY_AGENT]}},
        )

        if SUPPLY_AGENT in ENABLED_PRODUCTS:
            from app.seed.supply_agent import seed_supply_agent

            if await db.supplier_price_comparisons.count_documents({"tenant_id": tenant_id}) == 0:
                counts = await seed_supply_agent(db, tenant_id)
                print(
                    f"Seeded {counts['comparisons']} Supply Agent comparison rows "
                    f"and {counts['shoreline_catalog']} catalog rows",
                    flush=True,
                )
        print(f"Demo tenant ready (token: {result['api_token']})", flush=True)
    yield


app = FastAPI(
    title="BCA Hospitality Intelligence API",
    description="Independently licensed Margin IQ and Supply Agent products with an optional suite workspace.",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# All API routes live under /api so they can never collide with SPA client
# routes. Product routes are mounted independently and protected twice:
# deployment capability first, tenant entitlement second.
api = APIRouter(prefix="/api")
api.include_router(products.router)

if MARGIN_IQ in ENABLED_PRODUCTS:
    margin_dependencies = [Depends(require_product(MARGIN_IQ))]
    api.include_router(locations.router, dependencies=margin_dependencies)
    api.include_router(ingestion.router, dependencies=margin_dependencies)
    api.include_router(scan.router, dependencies=margin_dependencies)
    api.include_router(items.router, dependencies=margin_dependencies)
    api.include_router(recommendations.router, dependencies=margin_dependencies)
    api.include_router(dashboard.router, dependencies=margin_dependencies)
    api.include_router(validation.router, dependencies=margin_dependencies)
    api.include_router(exports.router, dependencies=margin_dependencies)
    api.include_router(engagement.router, dependencies=margin_dependencies)

if SUPPLY_AGENT in ENABLED_PRODUCTS:
    api.include_router(supply.router, dependencies=[Depends(require_product(SUPPLY_AGENT))])

app.include_router(api)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "bca-hospitality-intelligence-api",
        "product_mode": settings.product_mode,
        "enabled_products": sorted(ENABLED_PRODUCTS),
    }


if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """Serve the SPA for any non-API path."""
        candidate = STATIC_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
