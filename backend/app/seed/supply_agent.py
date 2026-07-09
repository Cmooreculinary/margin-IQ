"""Supply Agent seed data for Snakes & Lattes, extracted from Susan's US Foods
vs Shamrock price-comparison workbook plus supplier order guides.

Shoreline is loaded as a standalone catalog, not merged into the US Foods /
Shamrock comparison: Shoreline sells FOH disposables, syrups, and coffee-bar
supplies, not the same food products, so there is no valid item-for-item
price match against the other two vendors. Susan's own workbook explicitly
scoped Shoreline out of the comparison for the same reason ("Shoreline
removed").

Run directly:
    python -m app.seed.supply_agent
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.utils import new_id

COMPARISON_DATA_PATH = Path(__file__).parent / "data" / "us_foods_vs_shamrock.json"
SHORELINE_DATA_PATH = Path(__file__).parent / "data" / "shoreline_catalog.json"


async def seed_supply_agent(db, tenant_id: str) -> dict:
    comparison_rows = json.loads(COMPARISON_DATA_PATH.read_text())
    shoreline_rows = json.loads(SHORELINE_DATA_PATH.read_text())

    await db.supplier_price_comparisons.delete_many({"tenant_id": tenant_id})
    comparison_docs = []
    for row in comparison_rows:
        doc = dict(row)
        doc["_id"] = new_id()
        doc["tenant_id"] = tenant_id
        comparison_docs.append(doc)
    if comparison_docs:
        await db.supplier_price_comparisons.insert_many(comparison_docs)

    await db.supplier_catalog_items.delete_many({"tenant_id": tenant_id, "supplier": "Shoreline"})
    catalog_docs = []
    for row in shoreline_rows:
        doc = dict(row)
        doc["_id"] = new_id()
        doc["tenant_id"] = tenant_id
        doc["supplier"] = "Shoreline"
        catalog_docs.append(doc)
    if catalog_docs:
        await db.supplier_catalog_items.insert_many(catalog_docs)

    return {"comparisons": len(comparison_docs), "shoreline_catalog": len(catalog_docs)}


async def _main():
    from app.db import get_database
    from app.seed.snakes_and_lattes import TENANT_SLUG

    db = get_database()
    tenant = await db.tenants.find_one({"slug": TENANT_SLUG})
    if not tenant:
        raise SystemExit(f"Tenant '{TENANT_SLUG}' not found -- run app.seed.snakes_and_lattes first.")
    counts = await seed_supply_agent(db, tenant["_id"])
    print(f"Seeded {counts['comparisons']} price comparison rows and {counts['shoreline_catalog']} Shoreline catalog rows for tenant {tenant['_id']}.")


if __name__ == "__main__":
    asyncio.run(_main())
