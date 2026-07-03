"""Recommendation generation: item-level pricing moves (and menu-architecture
moves for weak items) with rationale, projected BPS lift, and a price-sensitivity
PMIX offset. Elasticity assumptions are editable per quadrant/segment -- this
is a transparent heuristic engine, not a black box."""
from __future__ import annotations

from dataclasses import dataclass

from app.services.prime_cost import ItemPrimeCost

# Price elasticity of demand by quadrant, editable by the operator per engagement.
# Negative: a price increase of X% is assumed to reduce volume by |E| * X%.
DEFAULT_ELASTICITY_BY_QUADRANT = {
    "star": -0.3,       # loyal demand, most price-tolerant
    "plowhorse": -0.6,  # popular but margin-thin; moderate sensitivity
    "puzzle": -0.5,     # low volume, decent margin; untested price tolerance
    "dog": -0.9,        # weakest position; most price-sensitive
}

MAX_PRICE_INCREASE_PCT = 0.12  # surgical changes only, never a broad hike
ROUND_TO = 0.25


def _round_price(price: float, *, floor_above: float | None = None) -> float:
    """Round to the nearest ROUND_TO increment. If that rounds back down to (or
    below) `floor_above` -- e.g. a small % bump on a low-priced item collapsing
    back to the sticker price -- bump up to the next increment instead."""
    rounded = round(round(price / ROUND_TO) * ROUND_TO, 2)
    if floor_above is not None and rounded <= floor_above:
        rounded = round(floor_above + ROUND_TO, 2)
    return rounded


@dataclass
class PriceSimulation:
    current_price: float
    recommended_price: float
    price_change_pct: float
    pmix_offset_pct: float  # projected volume change from elasticity, always <= 0 for a price rise
    projected_units: float
    projected_cm_dollars_total: float
    cm_dollars_lift: float
    projected_bps_lift: float  # lift in CM$ as bps of the item's baseline location revenue


def simulate_price_change(
    *,
    current_price: float,
    prime_cost: float,
    units_sold: int,
    new_price: float,
    elasticity: float,
    location_revenue_baseline: float,
) -> PriceSimulation:
    """Pure arithmetic on primitives -- deliberately not tied to ItemPrimeCost so
    the /decide endpoint can recompute a modified price from persisted scalars
    without having to fake up a whole item (a prior version did that with zeroed
    cost fields and silently used a stale, wrong baseline CM$)."""
    price_change_pct = (new_price - current_price) / current_price if current_price else 0.0
    volume_change_pct = elasticity * price_change_pct
    projected_units = max(units_sold * (1 + volume_change_pct), 0)

    baseline_cm_per_unit = current_price - prime_cost
    new_cm_per_unit = new_price - prime_cost
    baseline_cm_total = baseline_cm_per_unit * units_sold
    projected_cm_total = new_cm_per_unit * projected_units

    cm_lift = projected_cm_total - baseline_cm_total
    bps_lift = (
        round(cm_lift / location_revenue_baseline * 10000, 1)
        if location_revenue_baseline
        else 0.0
    )

    return PriceSimulation(
        current_price=current_price,
        recommended_price=new_price,
        price_change_pct=round(price_change_pct, 4),
        pmix_offset_pct=round(volume_change_pct, 4),
        projected_units=round(projected_units, 1),
        projected_cm_dollars_total=round(projected_cm_total, 2),
        cm_dollars_lift=round(cm_lift, 2),
        projected_bps_lift=bps_lift,
    )


def generate_recommendations(
    items: list[ItemPrimeCost],
    quadrant_by_plu: dict[str, str],
    *,
    location_revenue_baseline: float,
    location_median_prime_cost_pct: float,
    elasticity_by_quadrant: dict[str, float] | None = None,
) -> list[dict]:
    elasticity_by_quadrant = elasticity_by_quadrant or DEFAULT_ELASTICITY_BY_QUADRANT
    recs: list[dict] = []

    for item in items:
        quadrant = quadrant_by_plu.get(item.plu, "dog")
        elasticity = elasticity_by_quadrant.get(quadrant, -0.6)

        if item.is_food_cost_mirage:
            recs.append(
                {
                    "plu": item.plu,
                    "name": item.name,
                    "type": "reengineer",
                    "quadrant": quadrant,
                    "current_price": item.price,
                    "recommended_price": None,
                    "rationale": (
                        f"Food-cost mirage: {round((1 - item.food_cost_pct) * 100, 1)}% food-cost "
                        f"margin masks a {round((1 - item.prime_cost_pct) * 100, 1)}% prime-cost margin "
                        f"once labor is allocated. Recipe simplification or a labor-efficiency review "
                        f"will move the needle more than pricing alone."
                    ),
                    "projected_bps_lift": None,
                    "pmix_offset_pct": None,
                    "projected_cash_lift": None,
                }
            )
            continue

        if quadrant == "plowhorse":
            target_price = item.prime_cost / (1 - location_median_prime_cost_pct)
            target_price = max(target_price, item.price * 1.02)
            target_price = min(target_price, item.price * (1 + MAX_PRICE_INCREASE_PCT))
            new_price = _round_price(target_price, floor_above=item.price)
            sim = simulate_price_change(
                current_price=item.price,
                prime_cost=item.prime_cost,
                units_sold=item.units_sold,
                new_price=new_price,
                elasticity=elasticity,
                location_revenue_baseline=location_revenue_baseline,
            )
            recs.append(
                {
                    "plu": item.plu,
                    "name": item.name,
                    "type": "price",
                    "quadrant": quadrant,
                    "current_price": item.price,
                    "recommended_price": sim.recommended_price,
                    "rationale": (
                        f"High-volume plowhorse running {round(item.prime_cost_pct * 100, 1)}% prime "
                        f"cost vs. a {round(location_median_prime_cost_pct * 100, 1)}% location median. "
                        f"A surgical {round(sim.price_change_pct * 100, 1)}% increase closes most of the "
                        f"gap with minimal volume risk at this item's assumed elasticity."
                    ),
                    "projected_bps_lift": sim.projected_bps_lift,
                    "pmix_offset_pct": sim.pmix_offset_pct,
                    "projected_cash_lift": sim.cm_dollars_lift,
                }
            )
        elif quadrant == "puzzle":
            recs.append(
                {
                    "plu": item.plu,
                    "name": item.name,
                    "type": "reposition",
                    "quadrant": quadrant,
                    "current_price": item.price,
                    "recommended_price": None,
                    "rationale": (
                        "Strong per-unit margin but low popularity. Reposition on the menu "
                        "(placement, description, staff recommendation) or bundle with a Star "
                        "to build trial before touching price."
                    ),
                    "projected_bps_lift": None,
                    "pmix_offset_pct": None,
                    "projected_cash_lift": None,
                }
            )
        elif quadrant == "dog":
            recs.append(
                {
                    "plu": item.plu,
                    "name": item.name,
                    "type": "kill",
                    "quadrant": quadrant,
                    "current_price": item.price,
                    "recommended_price": None,
                    "rationale": (
                        "Low popularity and weak prime-cost margin. Candidate for removal, "
                        "recipe re-engineering, or a daypart shift rather than a price change."
                    ),
                    "projected_bps_lift": None,
                    "pmix_offset_pct": None,
                    "projected_cash_lift": None,
                }
            )
        # Stars with no mirage flag: no recommendation -- already performing.

    return recs
