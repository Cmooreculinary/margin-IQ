"""Running pro forma ticker: the live cumulative cash-flow impact of every
approved/modified recommendation, at both location and brand level, computed
before anything is actually committed to a live menu."""
from __future__ import annotations

from collections import defaultdict


def compute_pro_forma(recommendations: list[dict], *, period_days: int = 90) -> dict:
    """Each recommendation dict is expected to carry:
    status ('pending'|'approved'|'modified'|'denied'), location_id, location_name,
    projected_cash_lift (period $, may be None for non-price moves).
    Approved/modified recs count toward the ticker; pending/denied do not.
    """
    annualize_factor = 365 / period_days if period_days else 1

    counted_statuses = {"approved", "modified"}
    brand_period_total = 0.0
    by_location: dict[str, dict] = defaultdict(lambda: {"period_total": 0.0, "count": 0})

    approved_count = 0
    pending_count = 0
    denied_count = 0

    for rec in recommendations:
        status = rec.get("status", "pending")
        if status == "pending":
            pending_count += 1
        elif status == "denied":
            denied_count += 1
        elif status in counted_statuses:
            approved_count += 1
            cash_lift = rec.get("projected_cash_lift") or 0.0
            brand_period_total += cash_lift
            loc_id = rec.get("location_id", "unknown")
            by_location[loc_id]["period_total"] += cash_lift
            by_location[loc_id]["count"] += 1
            by_location[loc_id]["location_name"] = rec.get("location_name", loc_id)

    location_breakdown = [
        {
            "location_id": loc_id,
            "location_name": data.get("location_name", loc_id),
            "period_cash_impact": round(data["period_total"], 2),
            "annualized_cash_impact": round(data["period_total"] * annualize_factor, 2),
            "approved_recommendation_count": data["count"],
        }
        for loc_id, data in by_location.items()
    ]

    return {
        "brand_period_cash_impact": round(brand_period_total, 2),
        "brand_annualized_cash_impact": round(brand_period_total * annualize_factor, 2),
        "queue_progress": {
            "approved": approved_count,
            "pending": pending_count,
            "denied": denied_count,
            "total": len(recommendations),
        },
        "by_location": location_breakdown,
    }
