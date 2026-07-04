from datetime import datetime, timezone

import pytest

from app.services.prime_cost import compute_prime_cost
from app.services.validation import build_baseline_snapshot, measure_against_baseline


def _baseline():
    items = [
        compute_prime_cost(
            plu="A", name="Burger", category="Mains", daypart="dinner",
            price=10.0, food_cost=3.0, labor_cost=2.0, packaging_cost=0.5, units_sold=1000,
        ),
        compute_prime_cost(
            plu="B", name="Beer", category="Drinks", daypart="all_day",
            price=6.0, food_cost=1.0, labor_cost=0.5, packaging_cost=0.1, units_sold=2000,
        ),
    ]
    return build_baseline_snapshot(
        items,
        location_id="loc1",
        period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        period_end=datetime(2026, 3, 31, tzinfo=timezone.utc),
        signed_by="operator",
    )


def test_baseline_snapshot_totals():
    baseline = _baseline()
    # A: CM 4.5 * 1000 = 4500; B: CM 4.4 * 2000 = 8800
    assert baseline["cm_total"] == 13300.0
    assert baseline["revenue"] == 10 * 1000 + 6 * 2000
    assert baseline["signed_by"] == "operator"
    assert len(baseline["items"]) == 2


def test_bridge_components_sum_to_actual():
    baseline = _baseline()
    actuals = [
        {"plu": "A", "units_sold": 900, "gross_revenue": 900 * 10.5},  # +$0.50 implemented
        {"plu": "B", "units_sold": 1900, "gross_revenue": 1900 * 6.0},  # unchanged
    ]
    result = measure_against_baseline(
        baseline, actuals,
        seasonal_index_baseline=1.1, seasonal_index_post=0.9, food_inflation_pct=0.05,
    )
    b = result["bridge"]
    reconstructed = (
        b["baseline_cm"] + b["seasonality_effect"] + b["inflation_effect"]
        + b["price_effect"] + b["pmix_volume_effect"]
    )
    assert reconstructed == pytest.approx(b["actual_cm"], abs=0.05)


def test_price_effect_and_offset_pct():
    baseline = _baseline()
    actuals = [
        {"plu": "A", "units_sold": 1000, "gross_revenue": 1000 * 10.5},
        {"plu": "B", "units_sold": 2000, "gross_revenue": 2000 * 6.0},
    ]
    result = measure_against_baseline(baseline, actuals, food_inflation_pct=0.05)
    # price effect: +0.50 * 1000 units on A = 500
    assert result["bridge"]["price_effect"] == pytest.approx(500.0)
    # inflation headwind: 3.00*0.05*1000 + 1.00*0.05*2000 = 150 + 100 = 250
    assert result["bridge"]["inflation_effect"] == pytest.approx(-250.0)
    # offset: 500 / 250 = 200% of the food-inflation headwind offset by pricing
    assert result["offset_pct"] == pytest.approx(2.0)


def test_validated_bps_lift_is_margin_pct_based():
    baseline = _baseline()
    # Same volumes, +$0.50 on A, no inflation: CM% must rise -> positive BPS
    actuals = [
        {"plu": "A", "units_sold": 1000, "gross_revenue": 1000 * 10.5},
        {"plu": "B", "units_sold": 2000, "gross_revenue": 2000 * 6.0},
    ]
    result = measure_against_baseline(baseline, actuals)
    assert result["validated_bps_lift"] > 0


def test_new_and_discontinued_items_tracked():
    baseline = _baseline()
    actuals = [
        {"plu": "A", "units_sold": 1000, "gross_revenue": 10000.0},
        {"plu": "C", "units_sold": 50, "gross_revenue": 600.0, "item_name": "New Item"},
        # B missing -> discontinued
    ]
    result = measure_against_baseline(baseline, actuals)
    statuses = {row["plu"]: row["status"] for row in result["item_bridge"]}
    assert statuses["C"] == "new_since_baseline"
    assert statuses["B"] == "discontinued"
    assert statuses["A"] == "matched"
