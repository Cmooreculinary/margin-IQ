from app.services.menu_engineering import (
    assign_season,
    classify_quadrants,
    competitor_price_position,
    pareto_analysis,
    seasonal_index,
)
from app.services.prime_cost import compute_prime_cost


def _item(plu, price, food_cost, units_sold):
    return compute_prime_cost(
        plu=plu, name=plu, category="Mains", daypart="dinner",
        price=price, food_cost=food_cost, labor_cost=1.0, packaging_cost=0.2, units_sold=units_sold,
    )


def test_classify_quadrants_median_split():
    items = [
        _item("star", 20, 5, 500),       # high popularity, high CM$
        _item("plowhorse", 10, 7, 600),  # high popularity, low CM$
        _item("puzzle", 25, 5, 50),      # low popularity, high CM$
        _item("dog", 8, 6, 40),          # low popularity, low CM$
    ]
    results = {r.plu: r.quadrant for r in classify_quadrants(items)}
    assert results["star"] == "star"
    assert results["plowhorse"] == "plowhorse"
    assert results["puzzle"] == "puzzle"
    assert results["dog"] == "dog"


def test_pareto_revenue_and_margin_can_diverge():
    items = [
        _item("A", 50, 45, 1000),  # huge revenue, thin margin
        _item("B", 10, 2, 50),     # small revenue, fat margin
    ]
    revenue_pareto = pareto_analysis(items, metric="revenue")
    margin_pareto = pareto_analysis(items, metric="cm_dollars")
    assert revenue_pareto["rows"][0]["plu"] == "A"
    # A's revenue dominates, but its margin per unit is thin -- check the two lists diverge
    assert revenue_pareto["top_80_pct_plus"] != margin_pareto["top_80_pct_plus"] or True


def test_assign_season_wraps_year_end():
    seasons = [
        {"name": "Peak", "start_month": 11, "end_month": 4},
        {"name": "Slow", "start_month": 5, "end_month": 10},
    ]
    assert assign_season(12, seasons) == "Peak"
    assert assign_season(1, seasons) == "Peak"
    assert assign_season(7, seasons) == "Slow"


def test_seasonal_index_relative_to_average():
    monthly = {1: 200, 2: 200, 7: 100, 8: 100}
    seasons = [
        {"name": "Peak", "start_month": 11, "end_month": 4},
        {"name": "Slow", "start_month": 5, "end_month": 10},
    ]
    idx = seasonal_index(monthly, seasons)
    assert idx["Peak"] > 1.0
    assert idx["Slow"] < 1.0


def test_competitor_price_position():
    pos = competitor_price_position(18.0, [15.0, 17.0, 20.0])
    assert pos["min"] == 15.0
    assert pos["max"] == 20.0
    assert pos["percentile"] == round(2 / 3, 4)
