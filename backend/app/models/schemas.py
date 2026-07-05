"""Pydantic request/response schemas. Database documents are stored as plain dicts;
these models validate the boundary (API in/out), not the storage layer."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PrepComplexity(str, Enum):
    simple = "simple"
    moderate = "moderate"
    complex = "complex"


class Daypart(str, Enum):
    breakfast = "breakfast"
    brunch = "brunch"
    lunch = "lunch"
    dinner = "dinner"
    late_night = "late_night"
    all_day = "all_day"


class Quadrant(str, Enum):
    star = "star"
    plowhorse = "plowhorse"
    puzzle = "puzzle"
    dog = "dog"


class RecommendationType(str, Enum):
    price = "price"
    reposition = "reposition"
    bundle = "bundle"
    kill = "kill"
    reengineer = "reengineer"
    daypart_shift = "daypart_shift"


class RecommendationStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    modified = "modified"
    denied = "denied"


class MonitoringTier(str, Enum):
    essential = "essential"
    professional = "professional"
    executive = "executive"


# ---------- Tenant / Location / Item ----------

class TenantCreate(BaseModel):
    name: str
    slug: str
    monitoring_tier: MonitoringTier = MonitoringTier.essential


class LocationCreate(BaseModel):
    tenant_id: str
    name: str
    code: str
    sqft: Optional[int] = None
    concept_notes: Optional[str] = None
    daypart_hours: dict[str, str] = Field(default_factory=dict)


class Season(BaseModel):
    name: str
    start_month: int  # 1-12
    end_month: int  # 1-12, inclusive; wraps if end < start


class MenuItemCreate(BaseModel):
    tenant_id: str
    location_id: Optional[str] = None  # None => brand-wide master item
    plu: str
    name: str
    category: str
    price: float
    recipe_food_cost: float
    packaging_cost: float = 0.0
    prep_complexity: PrepComplexity = PrepComplexity.moderate
    daypart: Daypart = Daypart.all_day
    is_excluded: bool = False  # non-F&B PLU (cover fee, retail, etc.)


class PmixRow(BaseModel):
    location_id: str
    plu: str
    period_start: datetime
    period_end: datetime
    units_sold: int
    gross_revenue: float


class LaborMatrixEntry(BaseModel):
    tenant_id: str
    location_id: str
    daypart: Daypart
    hours: float
    blended_rate: float
    complexity_weights: dict[str, float] = Field(
        default_factory=lambda: {"simple": 0.7, "moderate": 1.0, "complex": 1.6}
    )


class FinancialsUpload(BaseModel):
    tenant_id: str
    location_id: str
    period_start: datetime
    period_end: datetime
    gross_sales: float
    food_cost_actual: float
    labor_cost_actual: float


# ---------- Reconciliation ----------

class ReconciliationResult(BaseModel):
    location_id: str
    period_start: datetime
    period_end: datetime
    pos_total: float
    reported_total: float
    variance_pct: float
    tolerance_pct: float
    passed: bool
    explanation: str


# ---------- Competitors ----------

class CompetitorEntry(BaseModel):
    tenant_id: str
    location_id: str
    competitor_name: str
    address: Optional[str] = None
    item_name: str
    price: float


# ---------- Document scanning ----------

class ScanRecord(BaseModel):
    target: str  # financials | menu_item | labor_matrix | pmix_row | competitor
    data: dict


class ScanCommit(BaseModel):
    records: list[ScanRecord]


# ---------- Recommendations / Approval ----------

class RecommendationDecision(BaseModel):
    status: RecommendationStatus
    final_price: Optional[float] = None
    decided_by: str
    note: Optional[str] = None
