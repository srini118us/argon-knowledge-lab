# NET-STD@v2: Network zoning standard

| Field | Value |
|---|---|
| Document | NET-STD |
| Version | v2 |
| Status | Current |
| Effective | 2025-09-01 |
| Supersedes | NET-STD@v1 |
| Owner | Network Engineering |

## 1. Zones

| Zone | Purpose | Examples |
|---|---|---|
| Z1 | Public facing | Customer web portal, public APIs |
| Z2 | Internal applications | Shipment service, notification service, analytics jobs |
| Z3 | High security | Payments platform, driver identity service, fleet control |

## 2. Egress

**NZ-1** Services in Z1 and Z2 may call external vendors through the integration gateway.

**NZ-2** Any outbound connection from a service in Z3 to an external destination must pass through the egress proxy. Direct internet egress from Z3 is prohibited.

**NZ-3** The egress proxy logs destination, volume and certificate details for every connection and is reviewed weekly by the security operations centre.

## Revision history

| Version | Date | Change |
|---|---|---|
| v2 | 2025-09-01 | Added NZ-2 egress proxy requirement for Z3 |
| v1 | 2023-02-14 | First issue |
