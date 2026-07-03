"""Labor allocation calibration: spread a location's actual labor cost across
menu items by prep-complexity tier x daypart volume. Operator-editable via the
complexity_weights on each labor_matrix entry -- nothing here is hardcoded."""
from __future__ import annotations

from collections import defaultdict

DEFAULT_WEIGHTS = {"simple": 0.7, "moderate": 1.0, "complex": 1.6}


def allocate_labor_cost_per_item(
    *,
    items: list[dict],  # each: {plu, daypart, prep_complexity, units_sold}
    labor_matrix: list[dict],  # each: {daypart, hours, blended_rate, complexity_weights}
) -> dict[str, float]:
    """Returns {plu: allocated_labor_cost_per_unit}."""
    daypart_labor_cost: dict[str, float] = {}
    daypart_weights: dict[str, dict] = {}
    for entry in labor_matrix:
        daypart = entry["daypart"]
        daypart_labor_cost[daypart] = entry["hours"] * entry["blended_rate"]
        daypart_weights[daypart] = entry.get("complexity_weights") or DEFAULT_WEIGHTS

    items_by_daypart: dict[str, list[dict]] = defaultdict(list)
    for item in items:
        items_by_daypart[item["daypart"]].append(item)

    result: dict[str, float] = {}
    for daypart, daypart_items in items_by_daypart.items():
        weights = daypart_weights.get(daypart, DEFAULT_WEIGHTS)
        total_labor_for_daypart = daypart_labor_cost.get(daypart, 0.0)

        total_weight = sum(
            weights.get(i["prep_complexity"], 1.0) * max(i["units_sold"], 0)
            for i in daypart_items
        )
        if total_weight <= 0:
            for i in daypart_items:
                result[i["plu"]] = 0.0
            continue

        for i in daypart_items:
            item_weight = weights.get(i["prep_complexity"], 1.0) * max(i["units_sold"], 0)
            item_share_of_labor = total_labor_for_daypart * (item_weight / total_weight)
            per_unit = item_share_of_labor / i["units_sold"] if i["units_sold"] else 0.0
            result[i["plu"]] = round(per_unit, 4)

    return result
