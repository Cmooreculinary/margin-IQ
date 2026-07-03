import pytest

from app.seed.rook_and_roast import EXCLUDED_PLUS, PERIOD_END, PERIOD_START, seed
from app.services.menu_engineering import classify_quadrants
from app.services.pipeline import build_location_item_metrics


@pytest.mark.asyncio
async def test_seed_produces_a_reconciled_mirage_demo(db):
    result = await seed(db)
    tenant_id = result["tenant_id"]
    location_ids = result["location_ids"]

    # Reconciliation gate passed for every location out of the box.
    recon_runs = await db.reconciliation_runs.find({"tenant_id": tenant_id}).to_list(length=None)
    assert len(recon_runs) == 3
    assert all(r["passed"] for r in recon_runs)

    # The cover fee is excluded from F&B PMIX math but was still ingested.
    chicago_id = location_ids["CHI"]
    cover_fee_rows = await db.pmix_records.find(
        {"tenant_id": tenant_id, "location_id": chicago_id, "plu": "9001"}
    ).to_list(length=None)
    assert len(cover_fee_rows) == 1
    assert "9001" in EXCLUDED_PLUS

    # Loaded Nachos should trip the food-cost mirage flag at every location.
    for code, location_id in location_ids.items():
        items = await build_location_item_metrics(
            db, tenant_id=tenant_id, location_id=location_id,
            period_start=PERIOD_START, period_end=PERIOD_END,
        )
        nachos = next(i for i in items if i.plu == "2001")
        assert nachos.is_food_cost_mirage is True, f"Loaded Nachos should be a mirage at {code}"

        quadrants = classify_quadrants(items)
        quadrant_names = {q.quadrant for q in quadrants}
        # a realistic catalog should produce more than one quadrant
        assert len(quadrant_names) > 1

    # Recommendations were pre-generated for the approval queue demo.
    recs = await db.recommendations.find({"tenant_id": tenant_id}).to_list(length=None)
    assert len(recs) > 0
    assert any(r["plu"] == "2001" and r["type"] == "reengineer" for r in recs)
