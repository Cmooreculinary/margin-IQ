from datetime import datetime, timezone

from app.services.reconciliation import compute_pos_total, reconcile


def test_compute_pos_total_excludes_flagged_plus():
    rows = [
        {"plu": "1001", "gross_revenue": 100.0},
        {"plu": "9001", "gross_revenue": 50.0},  # cover fee, excluded
    ]
    assert compute_pos_total(rows, exclude_plus={"9001"}) == 100.0
    assert compute_pos_total(rows) == 150.0


def test_reconcile_passes_within_tolerance():
    result = reconcile(
        location_id="loc1",
        period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        period_end=datetime(2026, 3, 31, tzinfo=timezone.utc),
        pos_total=100000.0,
        reported_gross_sales=101000.0,  # 1% variance
        tolerance_pct=2.0,
    )
    assert result["passed"] is True
    assert result["variance_pct"] == 0.99


def test_reconcile_fails_outside_tolerance():
    result = reconcile(
        location_id="loc1",
        period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        period_end=datetime(2026, 3, 31, tzinfo=timezone.utc),
        pos_total=100000.0,
        reported_gross_sales=90000.0,  # ~11% variance
        tolerance_pct=2.0,
    )
    assert result["passed"] is False
    assert "outside the" in result["explanation"]
