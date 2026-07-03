from app.services.labor_allocation import allocate_labor_cost_per_item


def test_labor_allocated_proportional_to_complexity_and_volume():
    items = [
        {"plu": "simple_high_volume", "daypart": "dinner", "prep_complexity": "simple", "units_sold": 1000},
        {"plu": "complex_low_volume", "daypart": "dinner", "prep_complexity": "complex", "units_sold": 100},
    ]
    labor_matrix = [
        {"daypart": "dinner", "hours": 100, "blended_rate": 20, "complexity_weights": {"simple": 0.7, "moderate": 1.0, "complex": 1.6}},
    ]
    result = allocate_labor_cost_per_item(items=items, labor_matrix=labor_matrix)

    total_labor = 100 * 20
    weight_simple = 0.7 * 1000
    weight_complex = 1.6 * 100
    total_weight = weight_simple + weight_complex

    expected_simple_per_unit = round((total_labor * weight_simple / total_weight) / 1000, 4)
    expected_complex_per_unit = round((total_labor * weight_complex / total_weight) / 100, 4)

    assert result["simple_high_volume"] == expected_simple_per_unit
    assert result["complex_low_volume"] == expected_complex_per_unit
    # per-unit labor cost for the complex item should be meaningfully higher
    assert result["complex_low_volume"] > result["simple_high_volume"]


def test_zero_units_does_not_divide_by_zero():
    items = [{"plu": "ghost", "daypart": "dinner", "prep_complexity": "simple", "units_sold": 0}]
    labor_matrix = [{"daypart": "dinner", "hours": 10, "blended_rate": 20}]
    result = allocate_labor_cost_per_item(items=items, labor_matrix=labor_matrix)
    assert result["ghost"] == 0.0
