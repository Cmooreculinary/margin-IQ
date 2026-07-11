"""Commercial product boundaries and tenant entitlements.

Margin IQ and Supply Agent share authentication and tenant identity, but their
routes are gated independently. PRODUCT_MODE controls which products are
available in a deployment; the tenant's ``products`` field controls which of
those products the customer is licensed to use.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import Depends, HTTPException, status

from app.auth import get_current_tenant
from app.config import settings

MARGIN_IQ = "margin_iq"
SUPPLY_AGENT = "supply_agent"

PRODUCT_ORDER = (MARGIN_IQ, SUPPLY_AGENT)
MODE_PRODUCTS = {
    "margin": frozenset({MARGIN_IQ}),
    "supply": frozenset({SUPPLY_AGENT}),
    "suite": frozenset({MARGIN_IQ, SUPPLY_AGENT}),
}

PRODUCT_CATALOG: dict[str, dict[str, Any]] = {
    MARGIN_IQ: {
        "name": "Margin IQ",
        "slug": "margin-iq",
        "description": "Prime-cost menu profitability, recommendations, approvals, and validation.",
        "standalone": True,
        "entry_path": "/margin",
        "api_prefixes": ["/api/items", "/api/recommendations", "/api/dashboard", "/api/validation"],
    },
    SUPPLY_AGENT: {
        "name": "Supply Agent",
        "slug": "supply-agent",
        "description": "Vendor comparison, catalog intelligence, confidence controls, and savings analysis.",
        "standalone": True,
        "entry_path": "/supply-agent",
        "api_prefixes": ["/api/supply"],
    },
}


def deployment_products() -> frozenset[str]:
    """Products physically enabled in this deployment."""
    return MODE_PRODUCTS[settings.product_mode]


def tenant_products(tenant: dict) -> frozenset[str]:
    """Licensed products for one tenant, clamped to deployment capabilities.

    Existing tenants without an explicit ``products`` field inherit the
    deployment mode for backward compatibility. New production tenants should
    always receive an explicit product list.
    """
    deployed = deployment_products()
    configured = tenant.get("products")
    if not configured:
        return deployed
    return frozenset(str(product) for product in configured if product in deployed)


def require_product(product: str) -> Callable:
    """FastAPI dependency that rejects access to an unlicensed product."""
    if product not in PRODUCT_CATALOG:
        raise ValueError(f"Unknown product key: {product}")

    async def _require_product(tenant: dict = Depends(get_current_tenant)) -> dict:
        if product not in tenant_products(tenant):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tenant is not licensed for {PRODUCT_CATALOG[product]['name']}",
            )
        return tenant

    return _require_product


def product_manifest(tenant: dict) -> dict:
    """Frontend-safe capability manifest for navigation and product routing."""
    enabled = tenant_products(tenant)
    suite_enabled = all(product in enabled for product in PRODUCT_ORDER)
    return {
        "deployment_mode": settings.product_mode,
        "tenant_id": str(tenant["_id"]),
        "tenant_name": tenant.get("name", ""),
        "license_source": "tenant" if tenant.get("products") else "deployment_default",
        "enabled_products": [product for product in PRODUCT_ORDER if product in enabled],
        "products": [
            {
                "key": product,
                **PRODUCT_CATALOG[product],
                "enabled": product in enabled,
            }
            for product in PRODUCT_ORDER
        ],
        "suite_enabled": suite_enabled,
        "integration": {
            "key": "margin_supply_bridge",
            "enabled": suite_enabled,
            "status": "contract_ready" if suite_enabled else "requires_both_products",
            "description": (
                "Shared tenant identity and product APIs are active. Approved supplier-cost "
                "handoffs can be added without coupling either product's core workflow."
            ),
        },
    }
