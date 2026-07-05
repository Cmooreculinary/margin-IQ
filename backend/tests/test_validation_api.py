"""End-to-end validation flow over the real app: lock the Q1 baseline for
Chicago, measure Q2 actuals (seeded with implemented price bumps + summer-slow
volumes), and check the bridge, offset %, and PDF deck endpoints."""
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.seed.snakes_and_lattes import (
    DEMO_TENANT_TOKEN,
    PERIOD_END,
    PERIOD_START,
    POST_PERIOD_END,
    POST_PERIOD_START,
    seed,
)


@pytest.mark.asyncio
async def test_validation_flow_and_pdf_decks(db):
    seed_result = await seed(db)
    chicago_id = seed_result["location_ids"]["CHI"]
    headers = {"Authorization": f"Bearer {DEMO_TENANT_TOKEN}"}
    q1 = {"period_start": PERIOD_START.isoformat(), "period_end": PERIOD_END.isoformat()}
    lock_params = {"location_id": chicago_id, **q1}
    measure_params = {
        "location_id": chicago_id,
        "post_period_start": POST_PERIOD_START.isoformat(),
        "post_period_end": POST_PERIOD_END.isoformat(),
    }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Lock requires acknowledgment
        resp = await client.post(
            "/api/validation/baseline/lock", params=lock_params,
            headers=headers, json={"signed_by": "operator", "acknowledged": False},
        )
        assert resp.status_code == 400

        resp = await client.post(
            "/api/validation/baseline/lock", params=lock_params,
            headers=headers, json={"signed_by": "operator", "acknowledged": True},
        )
        assert resp.status_code == 200
        assert resp.json()["signed_by"] == "operator"

        # Baselines are immutable -- second lock rejected
        resp = await client.post(
            "/api/validation/baseline/lock", params=lock_params,
            headers=headers, json={"signed_by": "operator", "acknowledged": True},
        )
        assert resp.status_code == 409

        # Measure Q2 against the locked Q1 baseline
        resp = await client.post(
            "/api/validation/measure", params=measure_params,
            headers=headers,
            json={
                "food_inflation_pct": 0.03,
                "seasonal_index_baseline": 1.1,
                "seasonal_index_post": 0.9,
            },
        )
        assert resp.status_code == 200
        result = resp.json()

        # Bridge must reconcile exactly
        b = result["bridge"]
        total = (
            b["baseline_cm"] + b["seasonality_effect"] + b["inflation_effect"]
            + b["price_effect"] + b["pmix_volume_effect"]
        )
        assert abs(total - b["actual_cm"]) < 0.05

        # Seeded scenario implemented +$0.25 on five items -> positive price effect
        assert b["price_effect"] > 0
        # 3% food inflation on a ~30% food-cost menu -> real headwind, partly offset
        assert result["offset_pct"] is not None and result["offset_pct"] > 0
        # Excluded cover-fee PLU stays out of validation math
        assert all(row["plu"] != "9001" for row in result["item_bridge"])

        resp = await client.get("/api/validation/runs", headers=headers, params={"location_id": chicago_id})
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        # PDF decks
        resp = await client.get("/api/exports/analysis-deck.pdf", headers=headers, params=q1)
        assert resp.status_code == 200
        assert resp.content[:5] == b"%PDF-"

        resp = await client.get("/api/exports/recommendations-deck.pdf", headers=headers, params=q1)
        assert resp.status_code == 200
        assert resp.content[:5] == b"%PDF-"
