"""Validation engine (Phase 5): baseline lock, post-implementation
treatment measurement, item-level P&L bridge, and the Offset % metric
(pricing lift as a % of the food-inflation headwind).

Design choices, stated plainly:
- Baselines are snapshots. Once locked (with a digital acknowledgment), the
  baseline never recomputes -- later recipe or price edits can't quietly move
  the goalposts.
- Actuals derive item price from PMIX (gross_revenue / units), not the menu
  master, so implemented price changes show up as *realized* prices even if
  the master hasn't been updated.
- Actual per-unit costs reuse the baseline's food/labor/packaging costs, with
  food cost scaled by the operator-documented inflation %. This isolates the
  menu moves being validated from unrelated cost drift; labor re-baselining is
  a Phase 6+ refinement.
- The bridge decomposes actual-vs-baseline CM$ into: seasonality, inflation,
  price moves, and a PMIX/volume residual. Components always sum exactly to
  the total delta -- the residual is defined that way on purpose, so nothing
  is ever silently unexplained.
"""
from __future__ import annotations

from datetime import datetime, timezone

from app.services.prime_cost import ItemPrimeCost


def build_baseline_snapshot(
    items: list[ItemPrimeCost],
    *,
    location_id: str,
    period_start: datetime,
    period_end: datetime,
    signed_by: str,
) -> dict:
    revenue = sum(i.revenue for i in items)
    cm_total = sum(i.cm_dollars * i.units_sold for i in items)
    return {
        "location_id": location_id,
        "period_start": period_start,
        "period_end": period_end,
        "signed_by": signed_by,
        "locked_at": datetime.now(timezone.utc),
        "revenue": round(revenue, 2),
        "cm_total": round(cm_total, 2),
        "cm_pct": round(cm_total / revenue, 4) if revenue else 0.0,
        "items": [
            {
                "plu": i.plu,
                "name": i.name,
                "category": i.category,
                "price": i.price,
                "food_cost": i.food_cost,
                "labor_cost": i.labor_cost,
                "packaging_cost": i.packaging_cost,
                "units_sold": i.units_sold,
                "cm_per_unit": i.cm_dollars,
            }
            for i in items
        ],
    }


def measure_against_baseline(
    baseline: dict,
    actuals: list[dict],  # each: {plu, units_sold, gross_revenue} from post-period PMIX
    *,
    seasonal_index_baseline: float = 1.0,
    seasonal_index_post: float = 1.0,
    food_inflation_pct: float = 0.0,
) -> dict:
    """Returns the P&L bridge, item-level rows, validated BPS lift, and Offset %."""
    baseline_items = {i["plu"]: i for i in baseline["items"]}
    actual_by_plu = {a["plu"]: a for a in actuals}

    b_cm_total = baseline["cm_total"]
    b_revenue = baseline["revenue"]

    a_revenue = 0.0
    a_cm_total = 0.0
    price_effect = 0.0
    inflation_headwind = 0.0
    item_rows = []

    for plu, actual in actual_by_plu.items():
        base = baseline_items.get(plu)
        units = actual["units_sold"]
        if units <= 0:
            continue
        avg_price = actual["gross_revenue"] / units

        if base is None:
            # New item since baseline: counts toward actuals but not toward the
            # price/inflation decomposition (no baseline costs to anchor to).
            a_revenue += actual["gross_revenue"]
            item_rows.append(
                {
                    "plu": plu,
                    "name": actual.get("item_name", plu),
                    "status": "new_since_baseline",
                    "baseline_cm_total": 0.0,
                    "actual_cm_total": None,
                    "delta": None,
                    "price_effect": 0.0,
                }
            )
            continue

        inflated_food = base["food_cost"] * (1 + food_inflation_pct)
        unit_cost = inflated_food + base["labor_cost"] + base["packaging_cost"]
        actual_cm = (avg_price - unit_cost) * units
        baseline_cm = base["cm_per_unit"] * base["units_sold"]

        a_revenue += actual["gross_revenue"]
        a_cm_total += actual_cm
        price_effect += (avg_price - base["price"]) * units
        inflation_headwind += base["food_cost"] * food_inflation_pct * units

        item_rows.append(
            {
                "plu": plu,
                "name": base["name"],
                "status": "matched",
                "baseline_cm_total": round(baseline_cm, 2),
                "actual_cm_total": round(actual_cm, 2),
                "delta": round(actual_cm - baseline_cm, 2),
                "price_effect": round((avg_price - base["price"]) * units, 2),
            }
        )

    for plu, base in baseline_items.items():
        if plu not in actual_by_plu:
            item_rows.append(
                {
                    "plu": plu,
                    "name": base["name"],
                    "status": "discontinued",
                    "baseline_cm_total": round(base["cm_per_unit"] * base["units_sold"], 2),
                    "actual_cm_total": 0.0,
                    "delta": round(-(base["cm_per_unit"] * base["units_sold"]), 2),
                    "price_effect": 0.0,
                }
            )

    # ---- Bridge ----
    season_factor = (
        seasonal_index_post / seasonal_index_baseline if seasonal_index_baseline else 1.0
    )
    seasonality_effect = b_cm_total * (season_factor - 1)
    inflation_effect = -inflation_headwind
    total_delta = a_cm_total - b_cm_total
    # residual = whatever price/season/inflation don't explain (mix + volume)
    pmix_volume_effect = total_delta - price_effect - seasonality_effect - inflation_effect

    b_cm_pct = b_cm_total / b_revenue if b_revenue else 0.0
    a_cm_pct = a_cm_total / a_revenue if a_revenue else 0.0
    validated_bps_lift = round((a_cm_pct - b_cm_pct) * 10000, 1)

    offset_pct = (
        round(price_effect / inflation_headwind, 4) if inflation_headwind > 0 else None
    )

    return {
        "measured_at": datetime.now(timezone.utc),
        "assumptions": {
            "seasonal_index_baseline": seasonal_index_baseline,
            "seasonal_index_post": seasonal_index_post,
            "food_inflation_pct": food_inflation_pct,
        },
        "baseline": {
            "revenue": round(b_revenue, 2),
            "cm_total": round(b_cm_total, 2),
            "cm_pct": round(b_cm_pct, 4),
        },
        "actual": {
            "revenue": round(a_revenue, 2),
            "cm_total": round(a_cm_total, 2),
            "cm_pct": round(a_cm_pct, 4),
        },
        "bridge": {
            "baseline_cm": round(b_cm_total, 2),
            "seasonality_effect": round(seasonality_effect, 2),
            "inflation_effect": round(inflation_effect, 2),
            "price_effect": round(price_effect, 2),
            "pmix_volume_effect": round(pmix_volume_effect, 2),
            "actual_cm": round(a_cm_total, 2),
        },
        "validated_bps_lift": validated_bps_lift,
        "offset_pct": offset_pct,
        "item_bridge": item_rows,
    }
