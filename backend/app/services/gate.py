"""Data-quality gate: analysis endpoints call this before touching PMIX/cost
data. Never analyze unreconciled data silently."""
from __future__ import annotations

from fastapi import HTTPException


async def require_reconciled(db, *, tenant_id: str, location_id: str) -> dict:
    latest = await db.reconciliation_runs.find(
        {"tenant_id": tenant_id, "location_id": location_id}
    ).sort("run_at", -1).to_list(length=1)
    if not latest:
        raise HTTPException(
            409,
            "This location has no reconciliation run on file. Run POST /ingestion/reconcile "
            "before requesting analysis.",
        )
    if not latest[0]["passed"]:
        raise HTTPException(
            409,
            f"This location's latest reconciliation failed ({latest[0]['variance_pct']}% variance, "
            f"tolerance {latest[0]['tolerance_pct']}%). Resolve the variance before analysis unlocks.",
        )
    return latest[0]
