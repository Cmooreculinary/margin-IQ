"""Menu engineering analysis: quadrant classification (Star/Plowhorse/Puzzle/Dog),
Pareto views (which items drive 80% of revenue vs. 80% of margin -- these are
different lists), and competitor price-position benchmarking."""
from __future__ import annotations

import statistics
from dataclasses import dataclass

from app.services.prime_cost import ItemPrimeCost


@dataclass
class QuadrantResult:
    plu: str
    name: str
    popularity: int
    cm_dollars: float
    quadrant: str


def classify_quadrants(
    items: list[ItemPrimeCost],
    *,
    popularity_threshold: float | None = None,
    margin_threshold: float | None = None,
) -> list[QuadrantResult]:
    """Median popularity (units sold) x median CM$ define the quadrant lines,
    matching classic menu-engineering methodology. Both thresholds are
    operator-configurable overrides."""
    if not items:
        return []

    pop_threshold = (
        popularity_threshold
        if popularity_threshold is not None
        else statistics.median(i.units_sold for i in items)
    )
    margin_thresh = (
        margin_threshold
        if margin_threshold is not None
        else statistics.median(i.cm_dollars for i in items)
    )

    results = []
    for i in items:
        high_popularity = i.units_sold >= pop_threshold
        high_margin = i.cm_dollars >= margin_thresh
        if high_popularity and high_margin:
            quadrant = "star"
        elif high_popularity and not high_margin:
            quadrant = "plowhorse"
        elif not high_popularity and high_margin:
            quadrant = "puzzle"
        else:
            quadrant = "dog"
        results.append(
            QuadrantResult(
                plu=i.plu,
                name=i.name,
                popularity=i.units_sold,
                cm_dollars=i.cm_dollars,
                quadrant=quadrant,
            )
        )
    return results


def pareto_analysis(items: list[ItemPrimeCost], *, metric: str = "revenue") -> dict:
    """metric: 'revenue' or 'cm_dollars'. Returns items sorted descending with
    cumulative share, plus the list of PLUs that make up the first 80%."""
    if metric not in ("revenue", "cm_dollars"):
        raise ValueError("metric must be 'revenue' or 'cm_dollars'")

    total = sum(getattr(i, metric) for i in items)
    ranked = sorted(items, key=lambda i: getattr(i, metric), reverse=True)

    rows = []
    cumulative = 0.0
    top_80_plus = []
    reached_80 = False
    for i in ranked:
        value = getattr(i, metric)
        cumulative += value
        cumulative_pct = round(cumulative / total, 4) if total else 0.0
        rows.append(
            {
                "plu": i.plu,
                "name": i.name,
                "value": round(value, 2),
                "cumulative_pct": cumulative_pct,
            }
        )
        if not reached_80:
            top_80_plus.append(i.plu)
        if cumulative_pct >= 0.80:
            reached_80 = True

    return {"metric": metric, "total": round(total, 2), "rows": rows, "top_80_pct_plus": top_80_plus}


def assign_season(month: int, seasons: list[dict]) -> str | None:
    """seasons: [{name, start_month, end_month}]. end_month < start_month wraps
    across year end (e.g. Nov-Apr)."""
    for season in seasons:
        start, end = season["start_month"], season["end_month"]
        if start <= end:
            if start <= month <= end:
                return season["name"]
        else:
            if month >= start or month <= end:
                return season["name"]
    return None


def seasonal_index(monthly_revenue: dict[int, float], seasons: list[dict]) -> dict[str, float]:
    """Revenue index per season relative to the all-season average (1.0 = average,
    1.2 = 20% above average). Used so baseline comparisons are season-matched
    instead of comparing a slow month to a peak month."""
    if not monthly_revenue:
        return {}
    overall_avg = statistics.mean(monthly_revenue.values())
    if overall_avg == 0:
        return {s["name"]: 1.0 for s in seasons}

    season_totals: dict[str, list[float]] = {}
    for month, revenue in monthly_revenue.items():
        season = assign_season(month, seasons)
        if season:
            season_totals.setdefault(season, []).append(revenue)

    return {
        season: round(statistics.mean(values) / overall_avg, 4)
        for season, values in season_totals.items()
    }


def competitor_price_position(item_price: float, competitor_prices: list[float]) -> dict:
    """Where an item's price sits relative to its comparable-segment competitor set."""
    if not competitor_prices:
        return {"percentile": None, "vs_avg_pct": None, "min": None, "max": None, "avg": None}
    avg = statistics.mean(competitor_prices)
    below = sum(1 for p in competitor_prices if p < item_price)
    percentile = round(below / len(competitor_prices), 4)
    return {
        "percentile": percentile,
        "vs_avg_pct": round((item_price - avg) / avg, 4) if avg else None,
        "min": min(competitor_prices),
        "max": max(competitor_prices),
        "avg": round(avg, 2),
    }
