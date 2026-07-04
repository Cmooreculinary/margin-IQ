"""PDF deliverable deck generation (reportlab): Analysis Deck and
Recommendations Deck. Every page is watermarked with tenant + timestamp, and
every projected figure is labeled as a projection -- validated results live in
the Validation module and are never mixed in here."""
from __future__ import annotations

import io
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

FIRE = colors.HexColor("#EC5B13")
OBSIDIAN = colors.HexColor("#0D0D0D")
GREY = colors.HexColor("#666666")
LIGHT = colors.HexColor("#F2F2F2")

_styles = getSampleStyleSheet()
H1 = ParagraphStyle("MarginH1", parent=_styles["Title"], textColor=OBSIDIAN, fontSize=26, spaceAfter=6)
H2 = ParagraphStyle("MarginH2", parent=_styles["Heading2"], textColor=FIRE, fontSize=15, spaceBefore=14)
BODY = ParagraphStyle("MarginBody", parent=_styles["Normal"], fontSize=9.5, leading=13)
FOOT = ParagraphStyle("MarginFoot", parent=_styles["Normal"], fontSize=7.5, textColor=GREY)
CELL = ParagraphStyle("MarginCell", parent=_styles["Normal"], fontSize=8, leading=10)


def _watermark_factory(tenant_name: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(GREY)
        canvas.drawString(
            0.75 * inch, 0.5 * inch,
            f"MARGIN IQ  |  {tenant_name}  |  Generated {ts}  |  CONFIDENTIAL",
        )
        canvas.drawRightString(letter[0] - 0.75 * inch, 0.5 * inch, f"Page {doc.page}")
        canvas.setFillColor(FIRE)
        canvas.rect(0, letter[1] - 0.18 * inch, letter[0], 0.18 * inch, stroke=0, fill=1)
        canvas.restoreState()

    return draw


def _table(header: list[str], rows: list[list], col_widths=None) -> Table:
    data = [header] + rows
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), OBSIDIAN),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return t


def _cover(story: list, *, deck_name: str, tenant_name: str, period_label: str):
    story.append(Spacer(1, 1.6 * inch))
    story.append(Paragraph("MARGIN IQ", ParagraphStyle("brand", parent=H1, textColor=FIRE, fontSize=34)))
    story.append(Paragraph(deck_name, H1))
    story.append(Spacer(1, 0.25 * inch))
    story.append(Paragraph(f"<b>{tenant_name}</b> &nbsp;·&nbsp; {period_label}", BODY))
    story.append(Spacer(1, 0.15 * inch))
    story.append(
        Paragraph(
            "All forward-looking figures in this deck are projections, not commitments. "
            "Validated results are reported separately by the Validation module.",
            FOOT,
        )
    )
    story.append(PageBreak())


def build_analysis_deck(
    *,
    tenant_name: str,
    period_label: str,
    brand_kpis: dict,
    location_sections: list[dict],
) -> bytes:
    """location_sections: [{name, kpis: dict, quadrant_counts: dict,
    top_items: [{name, cm_dollars_total, quadrant}], mirage_items: [{name, food_margin_pct, prime_margin_pct}]}]"""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.8 * inch, bottomMargin=0.9 * inch)
    story: list = []

    _cover(story, deck_name="ANALYSIS DECK", tenant_name=tenant_name, period_label=period_label)

    story.append(Paragraph("Brand Overview", H2))
    story.append(
        _table(
            ["Combined F&B Revenue", "Blended Prime Cost %", "Contribution Margin $", "Locations"],
            [[
                f"${brand_kpis['combined_revenue']:,.0f}",
                f"{brand_kpis['blended_prime_cost_pct'] * 100:.1f}%",
                f"${brand_kpis['combined_cm_dollars']:,.0f}",
                str(brand_kpis["location_count"]),
            ]],
        )
    )

    for section in location_sections:
        story.append(Paragraph(f"Location: {section['name']}", H2))
        k = section["kpis"]
        story.append(
            _table(
                ["Revenue", "Prime Cost %", "CM $", "Items Analyzed"],
                [[
                    f"${k['revenue']:,.0f}",
                    f"{k['prime_cost_pct'] * 100:.1f}%",
                    f"${k['cm_dollars']:,.0f}",
                    str(k["item_count"]),
                ]],
            )
        )
        story.append(Spacer(1, 0.12 * inch))
        qc = section["quadrant_counts"]
        story.append(
            _table(
                ["Stars", "Plowhorses", "Puzzles", "Dogs"],
                [[str(qc.get(q, 0)) for q in ("star", "plowhorse", "puzzle", "dog")]],
            )
        )
        story.append(Spacer(1, 0.12 * inch))
        story.append(Paragraph("Top Margin Drivers", ParagraphStyle("h3", parent=H2, fontSize=11, spaceBefore=6)))
        story.append(
            _table(
                ["Item", "Total CM $", "Quadrant"],
                [
                    [Paragraph(i["name"], CELL), f"${i['cm_dollars_total']:,.0f}", i["quadrant"].upper()]
                    for i in section["top_items"]
                ],
                col_widths=[3.4 * inch, 1.6 * inch, 1.4 * inch],
            )
        )
        if section["mirage_items"]:
            story.append(Paragraph("Food-Cost Mirage Flags", ParagraphStyle("h3b", parent=H2, fontSize=11, spaceBefore=6)))
            story.append(
                _table(
                    ["Item", "Food-Cost Margin", "Prime-Cost Margin"],
                    [
                        [Paragraph(m["name"], CELL), f"{m['food_margin_pct'] * 100:.1f}%", f"{m['prime_margin_pct'] * 100:.1f}%"]
                        for m in section["mirage_items"]
                    ],
                    col_widths=[3.4 * inch, 1.6 * inch, 1.6 * inch],
                )
            )

    doc.build(story, onFirstPage=_watermark_factory(tenant_name), onLaterPages=_watermark_factory(tenant_name))
    return buf.getvalue()


def build_recommendations_deck(
    *,
    tenant_name: str,
    period_label: str,
    pro_forma: dict,
    recs_by_location: dict[str, list[dict]],
) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, topMargin=0.8 * inch, bottomMargin=0.9 * inch)
    story: list = []

    _cover(story, deck_name="RECOMMENDATIONS DECK", tenant_name=tenant_name, period_label=period_label)

    story.append(Paragraph("Running Pro Forma", H2))
    qp = pro_forma["queue_progress"]
    story.append(
        _table(
            ["Approved Cash Impact (period)", "Annualized", "Approved", "Pending", "Denied"],
            [[
                f"${pro_forma['brand_period_cash_impact']:,.0f}",
                f"${pro_forma['brand_annualized_cash_impact']:,.0f}",
                str(qp["approved"]),
                str(qp["pending"]),
                str(qp["denied"]),
            ]],
        )
    )
    story.append(Paragraph(
        "Cash impact reflects operator-approved and operator-modified moves only. Projections, not validated results.",
        FOOT,
    ))

    for location_name, recs in recs_by_location.items():
        story.append(Paragraph(f"Location: {location_name}", H2))
        rows = []
        for r in recs:
            price_move = (
                f"${r['current_price']:.2f} → ${(r.get('final_price') or r['recommended_price']):.2f}"
                if r.get("recommended_price") is not None
                else "—"
            )
            bps = f"+{r['projected_bps_lift']:.0f}" if r.get("projected_bps_lift") else "—"
            rows.append(
                [
                    Paragraph(r["name"], CELL),
                    r["type"].upper(),
                    price_move,
                    bps,
                    r["status"].upper(),
                    Paragraph(r["rationale"], CELL),
                ]
            )
        story.append(
            _table(
                ["Item", "Move", "Price", "Proj. BPS", "Status", "Rationale"],
                rows,
                col_widths=[1.25 * inch, 0.85 * inch, 1.05 * inch, 0.65 * inch, 0.75 * inch, 2.45 * inch],
            )
        )

    doc.build(story, onFirstPage=_watermark_factory(tenant_name), onLaterPages=_watermark_factory(tenant_name))
    return buf.getvalue()
