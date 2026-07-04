from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import dashboard, engagement, exports, ingestion, items, locations, recommendations, validation

# Built frontend (copied in by the production Docker image). When present, this
# app serves the SPA too, so API + portal run as a single same-origin service.
STATIC_DIR = Path(os.environ.get("STATIC_DIR", "static"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.seed_demo:
        from app.db import get_database
        from app.seed.snakes_and_lattes import TENANT_SLUG, seed

        db = get_database()
        # Idempotent: add the demo tenant only when it is missing. This never
        # mutates an existing tenant and still lets an existing demo database get
        # the Snakes & Lattes account after deployment.
        if await db.tenants.count_documents({"slug": TENANT_SLUG}) == 0:
            result = await seed(db)
            print(f"Seeded Snakes & Lattes demo tenant (token: {result['api_token']})", flush=True)
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

app.include_router(locations.router)
app.include_router(ingestion.router)
app.include_router(items.router)
app.include_router(recommendations.router)
app.include_router(dashboard.router)
app.include_router(validation.router)
app.include_router(exports.router)
app.include_router(engagement.router)


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
