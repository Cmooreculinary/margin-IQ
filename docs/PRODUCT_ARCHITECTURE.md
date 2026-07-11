# Margin IQ + Supply Agent Product Architecture

## Commercial rule

Margin IQ and Supply Agent are independent products. Either can be licensed,
deployed, demonstrated, and operated without the other. The BCA IQ Suite enables
both products for the same tenant and adds a shared workspace without merging
their core workflows.

## Deployment modes

Set `PRODUCT_MODE` at runtime:

| Mode | Enabled product | Default use |
|---|---|---|
| `margin` | Margin IQ only | Menu profitability engagement |
| `supply` | Supply Agent only | Procurement / vendor intelligence engagement |
| `suite` | Both | Combined BCA engagement |

The repository ships three Render blueprints under `deploy/`. Each standalone
profile uses its own SQLite database path, so a customer can buy one product
without receiving or storing the other product's operating data.

## Tenant licensing

Each tenant may contain an explicit field:

```json
{
  "products": ["margin_iq", "supply_agent"]
}
```

Access is the intersection of:

1. products enabled by `PRODUCT_MODE`; and
2. products licensed in the tenant's `products` field.

Existing tenants without the field inherit the deployment mode for backward
compatibility. New production tenants should always receive an explicit list.

## Isolation guarantees

- Shared: bearer authentication, tenant identity, deployment image, product
  discovery endpoint, and optional suite navigation.
- Separate: API route groups, database collections, UI routes, commercial
  entitlement, and workflow ownership.
- Margin IQ cannot call Supply Agent routes for an unlicensed tenant.
- Supply Agent cannot call Margin IQ routes for an unlicensed tenant.
- A deployment that does not enable a product does not register that product's
  routes at all.

`GET /api/products` returns the authenticated tenant's capability manifest.
The frontend builds its routes and navigation from that response.

## Integration contract

Suite mode deliberately does not write supplier prices directly into recipe
costs. That would create an unsafe hidden coupling. The current bridge is
`contract_ready`: both products share a tenant and can be opened together, but
a supplier-cost handoff must later use an approved SKU-to-ingredient mapping,
a review step, and an audit log.

This preserves the product boundary while making the future workflow clear:

1. Supply Agent validates and approves a supplier cost.
2. A mapping contract identifies the affected ingredient or recipe input.
3. An operator approves the handoff.
4. Margin IQ recalculates prime cost and records the source and timestamp.

## API boundaries

- Margin IQ: `/api/locations`, `/api/ingestion`, `/api/items`,
  `/api/recommendations`, `/api/dashboard`, `/api/validation`, `/api/exports`,
  `/api/engagement`.
- Supply Agent: `/api/supply`.
- Shared discovery: `/api/products`.

## Release discipline

The previous Supply Agent implementation was merged into `main`, while the
newer Margin IQ platform lived on `claude/margin-iq-platform-7oov21`. This
modular merge resolves that divergence and supersedes the blocked direct merge
PR. Future product work should branch from the repository default branch and
must preserve the product gates.
