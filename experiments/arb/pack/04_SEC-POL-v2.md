# SEC-POL@v2: Security policy for external integrations

| Field | Value |
|---|---|
| Document | SEC-POL |
| Version | v2 |
| Status | Superseded |
| Effective | 2025-03-15 |
| Superseded by | SEC-POL@v3 (effective 2026-07-01) |
| Owner | Chief Information Security Officer |

## 1. Scope

This policy applies to every integration in which Northwind data is sent to, stored by, or processed by a third party vendor. Data classes are defined in DCS-01.

## 2. Vendor eligibility

**SP-2.1** A vendor may receive data only up to the highest class covered by its data processing agreement.

**SP-2.2** C3 data is never sent to a third party.

## 3. Data in transit

**SP-3.1** C3 data leaving the internal network must use mutual TLS. C2 data may use standard HTTPS with server side TLS.

## 4. Data at rest at the vendor

**SP-4.1** A vendor may retain C2 or higher data for at most 90 days after receipt.

**SP-4.2** A vendor must store C2 or higher data encrypted at rest.

## Revision history

| Version | Date | Change |
|---|---|---|
| v2 | 2025-03-15 | Added SP-4.2 encryption at rest |
| v1 | 2023-09-01 | First issue |
