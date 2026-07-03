from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import dashboard, ingestion, items, locations, recommendations

app = FastAPI(
    title="Margin IQ API",
    description="Menu profitability intelligence for multi-location F&B operators.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(locations.router)
app.include_router(ingestion.router)
app.include_router(items.router)
app.include_router(recommendations.router)
app.include_router(dashboard.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "margin-iq-api"}
