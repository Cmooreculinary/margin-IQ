from app.services.prime_cost import aggregate, compute_prime_cost


def test_basic_prime_cost_math():
    item = compute_prime_cost(
        plu="1001", name="Burger", category="Mains", daypart="dinner",
        price=20.0, food_cost=6.0, labor_cost=3.0, packaging_cost=1.0, units_sold=100,
    )
    assert item.prime_cost == 10.0
    assert item.prime_cost_pct == 0.5
    assert item.food_cost_pct == 0.3
    assert item.cm_dollars == 10.0
    assert item.cm_pct == 0.5
    assert item.revenue == 2000.0


def test_food_cost_mirage_flags_when_labor_heavy():
    # Cheap food, but labor eats the margin: 77% food margin, ~28% prime margin.
    mirage_item = compute_prime_cost(
        plu="2001", name="Loaded Nachos", category="Appetizers", daypart="dinner",
        price=13.0, food_cost=3.0, labor_cost=6.0, packaging_cost=0.3, units_sold=400,
    )
    assert mirage_item.is_food_cost_mirage is True

    normal_item = compute_prime_cost(
        plu="1002", name="Chicken Tenders", category="Mains", daypart="dinner",
        price=14.0, food_cost=4.2, labor_cost=2.4, packaging_cost=0.35, units_sold=900,
    )
    assert normal_item.is_food_cost_mirage is False


def test_aggregate_by_category():
    items = [
        compute_prime_cost(plu="1", name="A", category="Mains", daypart="dinner",
                           price=10, food_cost=3, labor_cost=1, packaging_cost=0.2, units_sold=100),
        compute_prime_cost(plu="2", name="B", category="Mains", daypart="dinner",
                           price=20, food_cost=6, labor_cost=2, packaging_cost=0.4, units_sold=50),
        compute_prime_cost(plu="3", name="C", category="Drinks", daypart="all_day",
                           price=5, food_cost=1, labor_cost=0.5, packaging_cost=0.1, units_sold=200),
    ]
    rolled_up = aggregate(items, "category")
    by_key = {row["category"]: row for row in rolled_up}
    assert set(by_key.keys()) == {"Mains", "Drinks"}
    mains_revenue = 10 * 100 + 20 * 50
    assert by_key["Mains"]["revenue"] == mains_revenue
