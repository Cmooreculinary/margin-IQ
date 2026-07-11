import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.products import MARGIN_IQ, SUPPLY_AGENT, product_manifest, tenant_products
from app.seed.snakes_and_lattes import DEMO_TENANT_TOKEN, seed
from app.seed.supply_agent import seed_supply_agent


def test_tenant_products_are_explicit_and_clamped(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "product_mode", "suite")
    assert tenant_products({"products": [MARGIN_IQ]}) == frozenset({MARGIN_IQ})
    assert tenant_products({"products": [SUPPLY_AGENT]}) == frozenset({SUPPLY_AGENT})
    assert tenant_products({"products": []}) == frozenset()
    assert tenant_products({"products": [MARGIN_IQ, SUPPLY_AGENT, "unknown"]}) == frozenset(
        {MARGIN_IQ, SUPPLY_AGENT}
    )


def test_product_manifest_marks_suite_contract_ready(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "product_mode", "suite")
    manifest = product_manifest(
        {
            "_id": "tenant-1",
            "name": "Test Tenant",
            "products": [MARGIN_IQ, SUPPLY_AGENT],
        }
    )
    assert manifest["suite_enabled"] is True
    assert manifest["integration"]["status"] == "contract_ready"
    assert manifest["enabled_products"] == [MARGIN_IQ, SUPPLY_AGENT]


@pytest.mark.asyncio
async def test_product_routes_are_tenant_gated(db):
    result = await seed(db)
    tenant_id = result["tenant_id"]
    await seed_supply_agent(db, tenant_id)
    headers = {"Authorization": f"Bearer {DEMO_TENANT_TOKEN}"}
    transport = ASGITransport(app=app)

    await db.tenants.update_one(
        {"_id": tenant_id},
        {"$set": {"products": [SUPPLY_AGENT]}},
    )
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        products = await client.get("/api/products", headers=headers)
        assert products.status_code == 200
        assert products.json()["enabled_products"] == [SUPPLY_AGENT]

        supply = await client.get("/api/supply/summary", headers=headers)
        assert supply.status_code == 200

        margin = await client.get("/api/locations", headers=headers)
        assert margin.status_code == 403

    await db.tenants.update_one(
        {"_id": tenant_id},
        {"$set": {"products": [MARGIN_IQ]}},
    )
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        margin = await client.get("/api/locations", headers=headers)
        assert margin.status_code == 200

        supply = await client.get("/api/supply/summary", headers=headers)
        assert supply.status_code == 403
