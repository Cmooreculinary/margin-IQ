"""Document scan flow: upload -> extraction (mocked) -> review -> commit.
The real Claude call is monkeypatched so these tests run offline; the live
integration is exercised manually with a real ANTHROPIC_API_KEY."""
import pytest
from httpx import ASGITransport, AsyncClient

import app.services.document_scan as document_scan
from app.main import app
from app.seed.snakes_and_lattes import DEMO_TENANT_TOKEN, seed

HEADERS = {"Authorization": f"Bearer {DEMO_TENANT_TOKEN}"}

FAKE_EXTRACTION = {
    "document_type": "financial_statement",
    "summary": "Monthly P&L for the Chicago location, January 2027.",
    "warnings": ["Labor cost line was partially obscured."],
    "records": [
        {
            "target": "financials",
            "data": {
                "location_hint": "Chicago",
                "period_start": "2027-01-01",
                "period_end": "2027-01-31",
                "gross_sales": 210500.0,
                "food_cost_actual": 63150.0,
                "labor_cost_actual": 71570.0,
            },
        }
    ],
}


@pytest.fixture
def client(db):
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_scan_upload_returns_extraction(db, client, monkeypatch):
    await seed(db)
    captured = {}

    async def fake_extract(data_b64, media_type, filename):
        captured.update(media_type=media_type, filename=filename)
        return dict(FAKE_EXTRACTION)

    monkeypatch.setattr(document_scan, "extract_document", fake_extract)

    async with client:
        resp = await client.post(
            "/api/ingestion/scan",
            headers=HEADERS,
            files={"file": ("pnl_jan.png", b"\x89PNG fake bytes", "image/png")},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["document_type"] == "financial_statement"
    assert body["filename"] == "pnl_jan.png"
    assert captured == {"media_type": "image/png", "filename": "pnl_jan.png"}


@pytest.mark.asyncio
async def test_scan_rejects_unsupported_type(db, client):
    await seed(db)
    async with client:
        resp = await client.post(
            "/api/ingestion/scan",
            headers=HEADERS,
            files={"file": ("data.xlsx", b"PK", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert resp.status_code == 415


@pytest.mark.asyncio
async def test_commit_writes_reviewed_records(db, client):
    seed_result = await seed(db)
    chicago_id = seed_result["location_ids"]["CHI"]

    records = [
        {
            "target": "financials",
            "data": {
                "location_id": chicago_id,
                "period_start": "2027-01-01T00:00:00",
                "period_end": "2027-01-31T00:00:00",
                "gross_sales": 210500.0,
                "food_cost_actual": 63150.0,
                "labor_cost_actual": 71570.0,
            },
        },
        {
            "target": "menu_item",
            "data": {
                "plu": "T7777",
                "name": "Truffle Fries",
                "category": "Sides",
                "price": 9.5,
                "recipe_food_cost": 2.6,
            },
        },
        {
            "target": "labor_matrix",
            "data": {"location_id": chicago_id, "daypart": "brunch", "hours": 80, "blended_rate": 19.0},
        },
    ]

    async with client:
        resp = await client.post("/api/ingestion/scan/commit", headers=HEADERS, json={"records": records})
    assert resp.status_code == 200, resp.text
    assert resp.json()["committed"] == {"financials": 1, "menu_item": 1, "labor_matrix": 1}

    tenant = await db.tenants.find_one({"api_token": DEMO_TENANT_TOKEN})
    fin = await db.financials.find_one({"tenant_id": tenant["_id"], "gross_sales": 210500.0})
    assert fin is not None and fin["location_id"] == chicago_id
    item = await db.menu_items.find_one({"tenant_id": tenant["_id"], "plu": "T7777"})
    assert item is not None and item["price"] == 9.5
    labor = await db.labor_matrix.find_one(
        {"tenant_id": tenant["_id"], "location_id": chicago_id, "daypart": "brunch"}
    )
    assert labor is not None and labor["blended_rate"] == 19.0


@pytest.mark.asyncio
async def test_commit_rejects_invalid_record_atomically(db, client):
    seed_result = await seed(db)
    chicago_id = seed_result["location_ids"]["CHI"]
    tenant = await db.tenants.find_one({"api_token": DEMO_TENANT_TOKEN})
    before = await db.menu_items.count_documents({"tenant_id": tenant["_id"]})

    records = [
        {"target": "menu_item", "data": {"plu": "9002", "name": "Ok Item", "category": "Sides", "price": 5.0, "recipe_food_cost": 1.0}},
        {"target": "financials", "data": {"location_id": chicago_id}},  # missing amounts -> invalid
    ]
    async with client:
        resp = await client.post("/api/ingestion/scan/commit", headers=HEADERS, json={"records": records})
    assert resp.status_code == 422
    # Nothing committed, including the valid record
    after = await db.menu_items.count_documents({"tenant_id": tenant["_id"]})
    assert after == before
