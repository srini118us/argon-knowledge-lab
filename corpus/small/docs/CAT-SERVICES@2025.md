---
Document ID: CAT-SERVICES
Version: 2025
Title: Orion service catalog 2025
Date: 2025-09-01
Status: Current
Supersedes: CAT-SERVICES 2024
---

# Orion service catalog 2025

This is the current catalog of services that make up the Orion order management platform at Northwind Logistics. It replaces the 2024 catalog (CAT-SERVICES 2024). If you are trying to find out who owns a service, who to page, or which service is responsible for a piece of business behaviour, start here.

The catalog answers one question per service: **which team owns it**. Ownership means the team is accountable for the service's code, its on-call rotation, its runbooks and its roadmap. Other teams may contribute changes, but the owning team reviews and approves them and carries the pager.

What this catalog does *not* cover: deployment details, recovery targets, dependencies between services and API contracts. Those live in the relevant ADRs, specifications and policies.

## What changed since 2024

There is one ownership change this year:

- **returns-service** moved from **Fulfillment** to **Commerce**.

The move reflects how returns actually work at Northwind now. Most of the complexity in a return is commercial (refund eligibility, partial credits, interaction with pricing and payments) rather than physical, and the Commerce team was already making the majority of changes to the service. Fulfillment remains closely involved where returns touch warehouse processes, but Commerce now holds the pager and approves changes.

All other owners are unchanged from the 2024 catalog.

## Ownership at a glance

| Service | Owning team |
|---|---|
| order-service | Fulfillment |
| inventory-service | Fulfillment |
| returns-service | Commerce (moved from Fulfillment) |
| pricing-service | Commerce |
| payment-service | Commerce |
| billing-service | Commerce |
| shipping-service | Logistics |
| carrier-gateway | Logistics |
| notification-service | Platform |
| identity-service | Platform |
| reporting-service | Data |
| customer-service | CRM |

Twelve services, six teams.

## Services by team

### Fulfillment

**order-service.** The heart of Orion. **order-service owns order creation and order cancellation.** Any system that wants to create an order or cancel one does so through order-service and its Order API; no other service may create or cancel orders directly, even if it holds enough data to do so. order-service is also the system of record for the order lifecycle and the source of order events on the event bus.

**inventory-service.** Tracks stock levels and stock reservations. It is the authority on what Northwind has available to sell and where it is held.

### Commerce

**returns-service.** Handles customer returns from request through to resolution. Owned by Commerce as of this catalog (previously Fulfillment, see above).

**pricing-service.** Calculates prices for orders, including any discounts and adjustments. Other services ask pricing-service for a price rather than computing their own.

**payment-service.** Handles customer payments, and is the only Orion component that integrates with PayNimbus, our payment gateway. See the PayNimbus integration specification for details of that boundary.

**billing-service.** Produces billing records and is responsible for the integration with LedgerOne, our ERP.

### Logistics

**shipping-service.** Manages shipments for orders and serves the Shipping API.

**carrier-gateway.** The single point of integration with SwiftShip, our carrier API vendor. Outbound behaviour towards SwiftShip is governed by ADR-024.

### Platform

**notification-service.** Sends notifications to customers and internal users on behalf of other services. Teams that need to notify someone call notification-service rather than integrating with delivery channels themselves.

**identity-service.** Provides identity and authentication for the platform, including the credentials services use to call each other.

Platform also owns the Kafka event bus itself. That is shared infrastructure rather than a service in this catalog, which is why it does not appear in the table.

### Data

**reporting-service.** Consumes events and data from across Orion and produces reporting for the business. It is a consumer of the platform, not something other services depend on at runtime.

### CRM

**customer-service.** Holds customer records and is responsible for the integration with Relatia, our CRM vendor.

## Reading an ownership entry

A few points that regularly cause confusion:

- **Ownership is per service, not per feature.** A business process often spans several services. Handling a return, for example, touches several services besides returns-service. Each service involved is owned by its own team, and the catalog does not try to describe the process end to end. If you need to know how a flow works, look at the relevant specification or ask the owning teams.
- **Vendor integrations belong to the service that holds them.** When a question is about PayNimbus, SwiftShip, Relatia or LedgerOne, the right owner is the team that owns the integrating service listed above, not whoever happened to raise the original contract.
- **Shared libraries are not services.** Client libraries and shared code used across Orion are maintained by the team that publishes them and are not tracked here.
- **The catalog follows reality, not org charts.** If a team is renamed or reorganised, the catalog is updated to match, but the services do not change hands unless an ownership move is agreed.

## How to use this catalog

**Paging.** If something is broken in a service, page the on-call for the owning team listed above. If you are not sure which service is at fault, page the team that owns the service closest to the symptom and let them route it.

**Changes to a service.** Open the change against the service's repository and request review from the owning team. Cross team changes are welcome, but they should be discussed with the owners first for anything beyond a small fix.

**New services.** A new service is not part of Orion until it has an owning team listed in this catalog. Add it here as part of onboarding, alongside the security and recovery checks required by platform policy.

**Ownership changes.** Ownership moves happen, as returns-service shows. They need agreement from both teams' leads, an updated catalog entry, and a handover of the on-call rotation, runbooks and open work. Do not change ownership informally by just starting to carry the pager; the catalog is the record.

## Corrections

If you spot an error in this catalog, raise it with the Platform team, who maintain the document. Do not edit ownership entries directly; changes to ownership need the agreement described above, and a new catalog version is published when the set of owners changes.
