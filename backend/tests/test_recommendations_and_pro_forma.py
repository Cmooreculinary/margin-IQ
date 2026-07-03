from app.services.prime_cost import compute_prime_cost
from app.services.pro_forma import compute_pro_forma
from app.services.recommendations import generate_recommendations, simulate_price_change


def test_plowhorse_gets_a_price_recommendation():
    plowhorse = compute_prime_cost(
        plu="1002", name="Chicken Tenders", category="Mains", daypart="dinner",
        price=14.0, food_cost=4.2, labor_cost=3.0, packaging_cost=0.35, units_sold=2000,
    )
    quadrant_by_plu = {"1002": "plowhorse"}
    recs = generate_recommendations(
        [plowhorse], quadrant_by_plu,
        location_revenue_baseline=28000.0,
        location_median_prime_cost_pct=0.45,
    )
    assert len(recs) == 1
    rec = recs[0]
    assert rec["type"] == "price"
    assert rec["recommended_price"] > rec["current_price"]
    # never a broad hike -- capped at 12%
    assert rec["recommended_price"] <= rec["current_price"] * 1.12 + 1e-6


def test_mirage_item_gets_reengineer_not_price_rec():
    mirage = compute_prime_cost(
        plu="2001", name="Loaded Nachos", category="Appetizers", daypart="dinner",
        price=13.0, food_cost=3.0, labor_cost=6.0, packaging_cost=0.3, units_sold=1200,
    )
    assert mirage.is_food_cost_mirage is True
    recs = generate_recommendations(
        [mirage], {"2001": "plowhorse"},
        location_revenue_baseline=15600.0,
        location_median_prime_cost_pct=0.45,
    )
    assert recs[0]["type"] == "reengineer"
    assert recs[0]["recommended_price"] is None


def test_dog_gets_kill_recommendation():
    dog = compute_prime_cost(
        plu="9999", name="Stale Item", category="Sides", daypart="dinner",
        price=8.0, food_cost=5.0, labor_cost=1.0, packaging_cost=0.2, units_sold=20,
    )
    recs = generate_recommendations(
        [dog], {"9999": "dog"},
        location_revenue_baseline=10000.0,
        location_median_prime_cost_pct=0.45,
    )
    assert recs[0]["type"] == "kill"


def test_pro_forma_only_counts_approved_and_modified():
    recs = [
        {"status": "pending", "location_id": "loc1", "location_name": "Chicago", "projected_cash_lift": 500},
        {"status": "approved", "location_id": "loc1", "location_name": "Chicago", "projected_cash_lift": 1000},
        {"status": "modified", "location_id": "loc2", "location_name": "Tempe", "projected_cash_lift": 250},
        {"status": "denied", "location_id": "loc2", "location_name": "Tempe", "projected_cash_lift": 9999},
    ]
    result = compute_pro_forma(recs, period_days=90)
    assert result["brand_period_cash_impact"] == 1250.0
    assert result["queue_progress"] == {"approved": 2, "pending": 1, "denied": 1, "total": 4}
    loc_ids = {row["location_id"] for row in result["by_location"]}
    assert loc_ids == {"loc1", "loc2"}


def test_simulate_price_change_reduces_volume_for_positive_elasticity_gap():
    sim = simulate_price_change(
        current_price=10.0, prime_cost=5.5, units_sold=1000,
        new_price=11.0, elasticity=-0.5, location_revenue_baseline=10000.0,
    )
    assert sim.pmix_offset_pct < 0
    assert sim.projected_units < 1000


def test_simulate_price_change_lift_is_positive_for_a_price_increase():
    # $10 price, $5.50 prime cost -> $4.50 baseline CM$/unit. Raising to $11
    # with mild elasticity should be a clear net gain, not a loss.
    sim = simulate_price_change(
        current_price=10.0, prime_cost=5.5, units_sold=1000,
        new_price=11.0, elasticity=-0.3, location_revenue_baseline=10000.0,
    )
    assert sim.cm_dollars_lift > 0
    assert sim.projected_bps_lift > 0
