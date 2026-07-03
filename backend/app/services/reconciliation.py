"""Reconciliation gate: imported PMIX revenue must tie out to reported financials
within tolerance before analysis unlocks. Pure functions -- no DB -- so they're
trivially unit-testable and reusable by whichever adapter fed the data in."""
from __future__ import annotations

from datetime import datetime


def compute_pos_total(pmix_rows: list[dict], exclude_plus: set[str] | None = None) -> float:
    """Sum gross_revenue across PMIX rows. Excluded (non-F&B) PLUs are left out
    of the reconciliation math by default -- they still show up in the raw
    revenue view, just not here."""
    exclude_plus = exclude_plus or set()
    return round(
        sum(r["gross_revenue"] for r in pmix_rows if r["plu"] not in exclude_plus), 2
    )


def reconcile(
    *,
    location_id: str,
    period_start: datetime,
    period_end: datetime,
    pos_total: float,
    reported_gross_sales: float,
    tolerance_pct: float = 2.0,
) -> dict:
    if reported_gross_sales == 0:
        variance_pct = 100.0 if pos_total else 0.0
    else:
        variance_pct = round(
            abs(pos_total - reported_gross_sales) / reported_gross_sales * 100, 2
        )
    passed = variance_pct <= tolerance_pct

    if passed:
        explanation = (
            f"POS total (${pos_total:,.2f}) matches reported financials "
            f"(${reported_gross_sales:,.2f}) within {tolerance_pct}% tolerance "
            f"({variance_pct}% variance). Analysis unlocked."
        )
    else:
        direction = "higher" if pos_total > reported_gross_sales else "lower"
        gap = abs(pos_total - reported_gross_sales)
        explanation = (
            f"POS total (${pos_total:,.2f}) is {variance_pct}% {direction} than reported "
            f"financials (${reported_gross_sales:,.2f}) -- a ${gap:,.2f} gap, outside the "
            f"{tolerance_pct}% tolerance. Common causes: missing PMIX days, un-excluded "
            f"non-F&B PLUs, or a reporting period mismatch. Analysis is locked until this "
            f"is resolved or the tolerance is adjusted."
        )

    return {
        "location_id": location_id,
        "period_start": period_start,
        "period_end": period_end,
        "pos_total": pos_total,
        "reported_total": reported_gross_sales,
        "variance_pct": variance_pct,
        "tolerance_pct": tolerance_pct,
        "passed": passed,
        "explanation": explanation,
    }
