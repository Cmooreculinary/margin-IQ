"""Document scanning: send an uploaded image or PDF to Claude and extract
structured records (financials, menu items, labor matrix, PMIX rows,
competitor prices) that the operator reviews before anything is committed.

Nothing here writes to the database -- extraction only. The commit step lives
in the scan router so the review-before-commit guardrail is enforced by the
API shape itself.
"""
from __future__ import annotations

import json

from anthropic import APIConnectionError, APIStatusError, AsyncAnthropic
from fastapi import HTTPException

from app.config import settings

MODEL = "claude-opus-4-8"

IMAGE_MEDIA_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
PDF_MEDIA_TYPE = "application/pdf"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024

# One flat record shape for all document types keeps the JSON schema simple
# (structured outputs require additionalProperties: false on every object).
# The commit step picks the fields relevant to each target.
_FIELD_TYPES: dict[str, str] = {
    "location_hint": "string",
    "plu": "string",
    "name": "string",
    "category": "string",
    "price": "number",
    "recipe_food_cost": "number",
    "packaging_cost": "number",
    "prep_complexity": "string",
    "daypart": "string",
    "period_start": "string",
    "period_end": "string",
    "gross_sales": "number",
    "food_cost_actual": "number",
    "labor_cost_actual": "number",
    "hours": "number",
    "blended_rate": "number",
    "units_sold": "integer",
    "gross_revenue": "number",
    "competitor_name": "string",
    "item_name": "string",
    "address": "string",
}

_RECORD_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["target", "data"],
    "properties": {
        "target": {
            "type": "string",
            "enum": ["financials", "menu_item", "labor_matrix", "pmix_row", "competitor"],
        },
        "data": {
            "type": "object",
            "additionalProperties": False,
            "required": sorted(_FIELD_TYPES),
            "properties": {
                field: {"anyOf": [{"type": type_name}, {"type": "null"}]}
                for field, type_name in _FIELD_TYPES.items()
            },
        },
    },
}

EXTRACTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["document_type", "summary", "warnings", "records"],
    "properties": {
        "document_type": {
            "type": "string",
            "enum": [
                "financial_statement",
                "menu",
                "labor_schedule",
                "pmix_report",
                "competitor_menu",
                "invoice",
                "unknown",
            ],
        },
        "summary": {"type": "string"},
        "warnings": {"type": "array", "items": {"type": "string"}},
        "records": {"type": "array", "items": _RECORD_SCHEMA},
    },
}

_SYSTEM_PROMPT = """\
You extract structured data from restaurant operations documents for Margin IQ,
a menu-profitability platform. The user uploads a photo, screenshot, or PDF of
one of the following, and you return the data it contains:

- financial_statement (P&L, sales summary) -> `financials` records with
  gross_sales, food_cost_actual, labor_cost_actual, period_start, period_end.
- menu (photo/PDF of a menu, or a recipe costing sheet) -> one `menu_item`
  record per item with name, category, price, and recipe_food_cost /
  packaging_cost when costs are shown.
- labor_schedule (schedule or payroll summary) -> `labor_matrix` records with
  daypart, hours, blended_rate. Dayparts: breakfast, brunch, lunch, dinner,
  late_night, all_day.
- pmix_report (POS product-mix report) -> one `pmix_row` per line with plu,
  item_name, units_sold, gross_revenue.
- competitor_menu (a competitor's menu or prices) -> `competitor` records with
  competitor_name, item_name, price.
- invoice (supplier invoice) -> treat line items as cost evidence: emit
  `menu_item` records ONLY when the document explicitly ties a cost to a menu
  item; otherwise summarize what the invoice contains and add a warning that
  invoice line items could not be mapped to menu items automatically.

Rules:
- Extract only values that are actually visible in the document. Never invent
  or estimate a number that is not there; leave the field null instead.
- Dates must be ISO format (YYYY-MM-DD). If the document names a location,
  put it in location_hint (the operator maps it to a real location on review).
- prep_complexity must be one of: simple, moderate, complex (or null).
- Money values are plain numbers with no currency symbols.
- Put anything ambiguous, low-confidence, or unreadable into warnings so the
  operator can double-check it during review.
- If the document is none of the above, use document_type "unknown", return no
  records, and explain what the document appears to be in the summary."""


def _client() -> AsyncAnthropic:
    if not settings.anthropic_api_key:
        raise HTTPException(
            503,
            "Document scanning is not configured: set the ANTHROPIC_API_KEY "
            "environment variable on the server.",
        )
    return AsyncAnthropic(api_key=settings.anthropic_api_key)


async def extract_document(data_b64: str, media_type: str, filename: str) -> dict:
    """Run Claude over a base64-encoded image/PDF and return the extraction
    result: {document_type, summary, warnings, records}."""
    if media_type == PDF_MEDIA_TYPE:
        file_block = {
            "type": "document",
            "source": {"type": "base64", "media_type": media_type, "data": data_b64},
        }
    else:
        file_block = {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": data_b64},
        }

    client = _client()
    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=_SYSTEM_PROMPT,
            output_config={"format": {"type": "json_schema", "schema": EXTRACTION_SCHEMA}},
            messages=[
                {
                    "role": "user",
                    "content": [
                        file_block,
                        {
                            "type": "text",
                            "text": f"Extract the data from this document (file name: {filename!r}).",
                        },
                    ],
                }
            ],
        )
    except APIStatusError as exc:
        # Surface the API's own message (e.g. "credit balance is too low",
        # rate limited) so the operator can act on it -- it never contains
        # secrets, only the error description.
        try:
            detail = exc.response.json()["error"]["message"]
        except Exception:
            detail = f"HTTP {exc.status_code}"
        raise HTTPException(502, f"Document scan failed: {detail}") from exc
    except APIConnectionError as exc:
        raise HTTPException(502, "Document scan failed: could not reach the AI service.") from exc
    finally:
        await client.close()

    if response.stop_reason == "refusal":
        raise HTTPException(422, "The document could not be processed. Try a different document.")

    text = next((b.text for b in response.content if b.type == "text"), None)
    if text is None:
        raise HTTPException(502, "Document scan failed: the AI service returned no output.")
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise HTTPException(502, "Document scan failed: could not parse the extraction output.") from exc
    # Drop null-valued fields so the review payloads only carry real data.
    for record in result.get("records", []):
        record["data"] = {k: v for k, v in record["data"].items() if v is not None}
    return result
