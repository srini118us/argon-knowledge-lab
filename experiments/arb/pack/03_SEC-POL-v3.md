# SEC-POL@v3: Security policy for external integrations

| Field | Value |
|---|---|
| Document | SEC-POL |
| Version | v3 |
| Status | Current |
| Effective | 2026-07-01 |
| Supersedes | SEC-POL@v2 |
| Owner | Chief Information Security Officer |

## 1. Scope

This policy applies to every integration in which Northwind data is sent to, stored by, or processed by a third party vendor. All vendors listed in the vendor register are third parties. Data classes are defined in DCS-01.

## 2. Vendor eligibility

**SP-2.1** A vendor may receive data only up to the highest class covered by its data processing agreement (DPA). The DPA is part of the vendor's contract.

**SP-2.2** C3 data is never sent to a third party, whatever its DPA says. Card numbers must be tokenized by the payments platform before any data leaves Northwind.

## 3. Data in transit

**SP-3.1** C2 or higher data leaving the internal network must use mutual TLS (mTLS) or a private link connection. Server side TLS alone (standard HTTPS) is not sufficient for C2 or higher data.

**SP-3.2** C1 data may use standard HTTPS.

## 4. Data at rest at the vendor

**SP-4.1** A vendor may retain C2 or higher data for at most 30 days after receipt. Regional annexes may set stricter limits.

**SP-4.2** A vendor must store C2 or higher data encrypted at rest.

**SP-4.3** C1 data has no retention or encryption requirement under this policy.

## 5. Exceptions

**SP-5.1** Exceptions to this policy are granted only through the exception register (EXC-REG) and apply only as the ARB charter describes.

## 6. Changes from v2

Version 3 tightened two controls after the 2026 external audit: mTLS or private link is now required for C2 data, not only for C3 data, and the vendor retention limit for C2 or higher data fell from 90 days to 30 days.

## Revision history

| Version | Date | Change |
|---|---|---|
| v3 | 2026-07-01 | SP-3.1 extended to C2; SP-4.1 reduced from 90 to 30 days |
| v2 | 2025-03-15 | Added SP-4.2 encryption at rest |
| v1 | 2023-09-01 | First issue |
