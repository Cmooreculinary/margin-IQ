"""Prime Cost Engine: food + labor + packaging cost per item, contribution
margin in $ and %, and the food-cost mirage flag -- items that look great on
food cost alone but bleed cash once labor is allocated in."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ItemPrimeCost:
    plu: str
    name: str
    category: str
    daypart: str
    price: float
    food_cost: float
    labor_cost: float
    packaging_cost: float
    units_sold: int

    prime_cost: float = field(init=False)
    prime_cost_pct: float = field(init=False)
    food_cost_pct: float = field(init=False)
    cm_dollars: float = field(init=False)
    cm_pct: float = field(init=False)
    revenue: float = field(init=False)
    is_food_cost_mirage: bool = field(init=False, default=False)

    def __post_init__(self):
        self.prime_cost = round(self.food_cost + self.labor_cost + self.packaging_cost, 4)
        self.food_cost_pct = round(self.food_cost / self.price, 4) if self.price else 0.0
        self.prime_cost_pct = round(self.prime_cost / self.price, 4) if self.price else 0.0
        self.cm_dollars = round(self.price - self.prime_cost, 4)
        self.cm_pct = round(self.cm_dollars / self.price, 4) if self.price else 0.0
        self.revenue = round(self.price * self.units_sold, 2)


MIRAGE_FOOD_MARGIN_FLOOR = 0.55  # item "looks" profitable on food cost alone
MIRAGE_MARGIN_GAP_PP = 0.25  # percentage-point gap between food margin and prime margin


def flag_food_cost_mirage(
    item: ItemPrimeCost,
    *,
    food_margin_floor: float = MIRAGE_FOOD_MARGIN_FLOOR,
    margin_gap_pp: float = MIRAGE_MARGIN_GAP_PP,
) -> bool:
    food_margin = 1 - item.food_cost_pct
    prime_margin = 1 - item.prime_cost_pct
    gap = food_margin - prime_margin
    is_mirage = food_margin >= food_margin_floor and gap >= margin_gap_pp
    item.is_food_cost_mirage = is_mirage
    return is_mirage


def compute_prime_cost(
    *,
    plu: str,
    name: str,
    category: str,
    daypart: str,
    price: float,
    food_cost: float,
    labor_cost: float,
    packaging_cost: float,
    units_sold: int,
) -> ItemPrimeCost:
    item = ItemPrimeCost(
        plu=plu,
        name=name,
        category=category,
        daypart=daypart,
        price=price,
        food_cost=food_cost,
        labor_cost=labor_cost,
        packaging_cost=packaging_cost,
        units_sold=units_sold,
    )
    flag_food_cost_mirage(item)
    return item


def aggregate(items: list[ItemPrimeCost], key: str) -> list[dict]:
    """Roll up CM$/CM% and blended prime cost % by an item attribute
    (category, daypart) or across the whole location when key='__all__'."""
    buckets: dict[str, list[ItemPrimeCost]] = {}
    for i in items:
        bucket_key = "__all__" if key == "__all__" else getattr(i, key)
        buckets.setdefault(bucket_key, []).append(i)

    out = []
    for bucket_key, bucket_items in buckets.items():
        revenue = sum(i.revenue for i in bucket_items)
        prime_cost_total = sum(i.prime_cost * i.units_sold for i in bucket_items)
        cm_total = sum(i.cm_dollars * i.units_sold for i in bucket_items)
        out.append(
            {
                key: bucket_key,
                "revenue": round(revenue, 2),
                "prime_cost_pct": round(prime_cost_total / revenue, 4) if revenue else 0.0,
                "cm_dollars": round(cm_total, 2),
                "cm_pct": round(cm_total / revenue, 4) if revenue else 0.0,
                "item_count": len(bucket_items),
            }
        )
    return out
