import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.seed.snakes_and_lattes import DEMO_TENANT_TOKEN, EXCLUDED_PLUS, PERIOD_END, PERIOD_START, seed
from app.services.menu_engineering import classify_quadrants
from app.services.pipeline import build_location_item_metrics


@pytest.mark.asyncio
async def test_snakes_and_lattes_seed_is_a_full_scale_demo(db):
    result = await seed(db)
    tenant_id = result["tenant_id"]
    location_ids = result["location_ids"]

    assert result["api_token"] == DEMO_TENANT_TOKEN
    assert set(location_ids) == {"CHI", "TMP", "TUC"}

    plan = await db.engagement_plans.find_one({"tenant_id": tenant_id})
    assert plan["brand_name"] == "Snakes & Lattes"
    assert len(plan["timeline"]) == 5
    assert any("Toast POS PMIX" in item for item in plan["data_requirements"])
    assert any(d["name"] == "Validation Deck" for d in plan["deliverables"])

    recon_runs = await db.reconciliation_runs.find({"tenant_id": tenant_id}).to_list(length=None)
    assert len(recon_runs) == 6
    assert all(r["passed"] for r in recon_runs)

    tempe_id = location_ids["TMP"]
    cover_fee_rows = await db.pmix_records.find(
        {"tenant_id": tenant_id, "location_id": tempe_id, "plu": "9001"}
    ).to_list(length=None)
    assert len(cover_fee_rows) == 2
    assert "9001" in EXCLUDED_PLUS

    combined_revenue = 0.0
    for code, location_id in location_ids.items():
        items = await build_location_item_metrics(
            db,
            tenant_id=tenant_id,
            location_id=location_id,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
        )
        assert all(i.plu != "9001" for i in items)
        assert any(i.is_food_cost_mirage for i in items), f"Expected at least one mirage item at {code}"
        assert len({q.quadrant for q in classify_quadrants(items)}) > 1
        combined_revenue += sum(i.revenue for i in items)

    assert 1_200_000 <= combined_revenue <= 1_300_000

    recs = await db.recommendations.find({"tenant_id": tenant_id}).to_list(length=None)
    assert len(recs) > 0
    assert any(r["type"] == "price" for r in recs)
    assert any(r["type"] == "reengineer" for r in recs)


@pytest.mark.asyncio
async def test_engagement_plan_endpoint(db):
    await seed(db)
    headers = {"Authorization": f"Bearer {DEMO_TENANT_TOKEN}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/engagement/plan", headers=headers)

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["tenant"]["name"] == "Snakes & Lattes - US"
    assert payload["plan"]["scope"]["locations"] == ["Chicago, IL", "Tempe, AZ", "Tucson, AZ"]
    assert payload["plan"]["terms"]["project_fee"] == 9900
