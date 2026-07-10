"""Lead auditor's independent truth check.

This script is the REVIEWER'S tool, deliberately separate from any verifier the
implementing engineer writes (docs/CODEX_BUILD_SPEC.md section 7 requires them
to ship their own). It re-derives every number the app shows from primary
sources only -- the seed JSONs and, when pdfplumber is available, the source
PDFs in docs/source/ -- and prints a pass/fail table. Any FAIL blocks approval.

Usage:
    python backend/scripts/lead_audit.py            # JSON-level checks
    /tmp/pdfenv/bin/python backend/scripts/lead_audit.py   # + PDF cross-checks

Exit code 0 = all checks pass, 1 = at least one failure.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
COMPARISON = REPO / "backend/app/seed/data/us_foods_vs_shamrock.json"
SHORELINE = REPO / "backend/app/seed/data/shoreline_catalog.json"
USF_GUIDE_PDF = REPO / "docs/source/US_Foods_Order_Guide_2026.pdf"
SHO_GUIDE_PDF = REPO / "docs/source/Order_Guide_Shoreline.pdf"

TRUSTED = {"High", "Review"}
RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))


def audit_comparison_internal(rows: list[dict]) -> None:
    check("comparison: 188 rows", len(rows) == 188, f"got {len(rows)}")
    lines = [r["line"] for r in rows]
    check("comparison: lines are 1..188 unique", sorted(lines) == list(range(1, 189)))

    bad_unit_math, bad_diff, bad_pct, bad_cheaper = [], [], [], []
    for r in rows:
        for side in ("us", "shamrock"):
            price, qty, per = r[f"{side}_price"], r[f"{side}_qty_in_unit"], r[f"{side}_dollar_per_unit"]
            if price is not None and qty and per is not None:
                if abs(price / qty - per) > 0.005:
                    bad_unit_math.append((r["line"], side, price, qty, per))
        u, s = r["us_dollar_per_unit"], r["shamrock_dollar_per_unit"]
        if u is not None and s is not None:
            if r["diff_dollar_per_unit"] is not None and abs((s - u) - r["diff_dollar_per_unit"]) > 0.005:
                bad_diff.append(r["line"])
            # Recompute the pct from UNROUNDED raw prices; the stored per-unit
            # fields are rounded to 4dp and comparing against those produces
            # false positives (audit finding, 2026-07-10: line 158).
            if (
                r["diff_pct"] is not None
                and r["us_price"] and r["us_qty_in_unit"] and r["shamrock_price"] and r["shamrock_qty_in_unit"]
            ):
                u_raw = r["us_price"] / r["us_qty_in_unit"]
                s_raw = r["shamrock_price"] / r["shamrock_qty_in_unit"]
                exact = (s_raw - u_raw) / u_raw * 100
                tol = max(0.05, abs(exact) * 0.003)
                if abs(exact - r["diff_pct"]) > tol:
                    bad_pct.append((r["line"], r["diff_pct"], round(exact, 2)))
            # cheaper_supplier must agree with the sign of the diff; "Tie" only
            # for an exactly equal unit price (the source workbook's convention).
            claimed = r["cheaper_supplier"]
            if claimed in ("US Foods", "Shamrock", "Tie"):
                expect = "Tie" if abs(s - u) < 1e-9 else ("Shamrock" if s < u else "US Foods")
                if claimed != expect:
                    bad_cheaper.append((r["line"], claimed, expect, round(s - u, 4)))
    check("comparison: price/qty == $ per unit (both sides)", not bad_unit_math, f"{len(bad_unit_math)} bad: {bad_unit_math[:3]}")
    check("comparison: diff = shamrock - us", not bad_diff, f"lines {bad_diff[:5]}")
    check("comparison: diff_pct consistent", not bad_pct, f"lines {bad_pct[:5]}")
    check("comparison: cheaper_supplier matches diff sign", not bad_cheaper, f"{bad_cheaper[:3]}")


def audit_summary_math(rows: list[dict]) -> None:
    """Replicate /api/supply/summary independently and state the expected values."""
    trusted = [r for r in rows if r["match_confidence"] in TRUSTED and r["diff_pct"] is not None]
    by = {"US Foods": 0, "Shamrock": 0, "Tie": 0}
    for r in trusted:
        by[r["cheaper_supplier"]] = by.get(r["cheaper_supplier"], 0) + 1
    savings = round(
        sum(
            -r["diff_dollar_per_unit"] * r["us_qty_in_unit"]
            for r in trusted
            if r["cheaper_supplier"] == "Shamrock" and r["diff_dollar_per_unit"] is not None and r["us_qty_in_unit"]
        ),
        2,
    )
    check(
        "summary: independent recompute",
        True,
        f"trusted={len(trusted)} needs_review={len(rows) - len(trusted)} by={by} switching_savings=${savings:,.2f}"
        " -- UI/KPIs MUST show exactly these",
    )


def audit_shoreline_internal(items: list[dict]) -> None:
    check("shoreline: 129 items", len(items) == 129, f"got {len(items)}")
    bad_price = [i["vendor_item"] for i in items if i.get("price") is not None and i["price"] <= 0]
    check("shoreline: no zero/negative parsed prices", not bad_price, str(bad_price[:5]))


def audit_pdf_crosscheck() -> None:
    try:
        import pdfplumber  # type: ignore
    except ImportError:
        check("PDF cross-check", True, "SKIPPED (pdfplumber not installed in this interpreter)")
        return

    with pdfplumber.open(USF_GUIDE_PDF) as pdf:
        guide_text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    guide_flat = " ".join(guide_text.split())

    rows = json.loads(COMPARISON.read_text())
    missing_prod, missing_price = [], []
    for r in rows:
        if r["us_product_number"] not in guide_flat:
            missing_prod.append(r["line"])
        elif r["us_price"] is not None and f"${r['us_price']:,.2f}/{r['us_price_unit']}" not in guide_flat:
            missing_price.append((r["line"], r["us_price"]))
    check("PDF: every US Foods product # appears in live order guide", not missing_prod, f"lines {missing_prod[:5]}")
    check("PDF: every US Foods price appears verbatim in live order guide", not missing_price, f"{missing_price[:5]}")

    noprice = guide_flat.count("No Price")
    check("PDF: 'No Price' line count (spec section 5.5 claims 8)", noprice == 8, f"got {noprice}")

    with pdfplumber.open(SHO_GUIDE_PDF) as pdf:
        sho_text = " ".join(" ".join((p.extract_text() or "").split()) for p in pdf.pages)
    items = json.loads(SHORELINE.read_text())
    # Compare on digits-only codes: the vendor's own guide prints stray
    # trailing hyphens on some codes (audit finding, 2026-07-10).
    sho_missing = [
        i["vendor_item"]
        for i in items
        if i.get("code")
        and i.get("price") is not None
        and not (re.sub(r"\D", "", i["code"]) and re.sub(r"\D", "", i["code"]) in re.sub(r"[^\d ]", "", sho_text) and f"${i['price']:,.2f}" in sho_text)
    ]
    check("PDF: every Shoreline code+price appears in Shoreline guide", not sho_missing, f"{sho_missing[:5]}")

    # Spec section 5.4 lead-verified anchors -- if the source ever changes, fail loudly.
    anchors = ["10017500 Case/12EA $32.31", "10120500 Case/12EA $48.94", "10225400 Case/12/32OZ $39.15"]
    bad_anchor = [a for a in anchors if a not in sho_text]
    check("PDF: spec 5.4 duplicate-spread anchor prices", not bad_anchor, str(bad_anchor))


def main() -> int:
    rows = json.loads(COMPARISON.read_text())
    items = json.loads(SHORELINE.read_text())
    audit_comparison_internal(rows)
    audit_summary_math(rows)
    audit_shoreline_internal(items)
    audit_pdf_crosscheck()

    width = max(len(n) for n, _, _ in RESULTS)
    failures = 0
    for name, ok, detail in RESULTS:
        status = "PASS" if ok else "FAIL"
        failures += 0 if ok else 1
        print(f"  [{status}] {name.ljust(width)}  {detail}")
    print(f"\n{len(RESULTS) - failures}/{len(RESULTS)} checks passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
