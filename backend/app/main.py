from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import dashboard, engagement, exports, ingestion, items, locations, recommendations, supply, validation

# Built frontend (copied in by the production Docker image). When present, this
# app serves the SPA too, so API + portal run as a single same-origin service.
STATIC_DIR = Path(os.environ.get("STATIC_DIR", "static"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.seed_demo:
        from app.db import get_database, verify_database_connection
        from app.seed.snakes_and_lattes import TENANT_SLUG, seed
        from app.seed.supply_agent import seed_supply_agent

        await verify_database_connection()
        db = get_database()
        # Idempotent: add the demo tenant only when it is missing. This never
        # mutates an existing tenant and still lets an existing demo database get
        # the Snakes & Lattes account after deployment.
        if await db.tenants.count_documents({"slug": TENANT_SLUG}) == 0:
            result = await seed(db)
            print(f"Seeded Snakes & Lattes demo tenant (token: {result['api_token']})", flush=True)
            tenant_id = result["tenant_id"]
        else:
            tenant_id = (await db.tenants.find_one({"slug": TENANT_SLUG}))["_id"]

        # Idempotent: (re)load Supply Agent comparison data only when missing,
        # so a redeploy never clobbers rows an operator has since edited.
        if await db.supplier_price_comparisons.count_documents({"tenant_id": tenant_id}) == 0:
            counts = await seed_supply_agent(db, tenant_id)
            print(
                f"Seeded {counts['comparisons']} Supply Agent price comparison rows "
                f"and {counts['shoreline_catalog']} Shoreline catalog rows",
                flush=True,
            )
    yield


app = FastAPI(
    title="Margin IQ API",
    description="Menu profitability intelligence for multi-location F&B operators.",
    version="0.1.0",
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
# routes (e.g. GET /items the API vs. /items the portal page).
api = APIRouter(prefix="/api")
api.include_router(locations.router)
api.include_router(ingestion.router)
api.include_router(items.router)
api.include_router(recommendations.router)
api.include_router(dashboard.router)
api.include_router(validation.router)
api.include_router(exports.router)
api.include_router(engagement.router)
api.include_router(supply.router)
app.include_router(api)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "margin-iq-api"}


if STATIC_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):
        """Serve the SPA for any non-API path. API routes are registered above,
        so they always win; this only catches client-side routes and /."""
        candidate = STATIC_DIR / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(STATIC_DIR / "index.html")
