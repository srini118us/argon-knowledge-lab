**Document ID:** CAT-SERVICES
**Version:** 2024
**Title:** Orion service catalog 2024
**Date:** 2024-06-30
**Status:** Superseded
**Superseded by:** CAT-SERVICES 2025

> This catalog has been superseded by CAT-SERVICES 2025. Ownership of at least one service has changed since this edition. Use the 2025 catalog for current owners.

# Orion service catalog 2024

## About this catalog

This catalog lists the services that make up the Orion order management platform at Northwind Logistics and the team that owns each one. "Owns" means the team is accountable for the service's code, its deployments, its on-call rotation, and its roadmap. If something is wrong with a service, the owning team is where the conversation starts.

The catalog is refreshed periodically. Between refreshes, ownership changes are agreed through architecture review and recorded when the next edition is published.

## Teams at a glance

| Team | Services owned |
|---|---|
| Fulfillment | order-service, inventory-service, returns-service |
| Commerce | pricing-service, payment-service, billing-service |
| Logistics | shipping-service, carrier-gateway |
| Platform | notification-service, identity-service |
| Data | reporting-service |
| CRM | customer-service |

## Service catalog

| Service | Owning team | Summary |
|---|---|---|
| order-service | Fulfillment | Order lifecycle on the Orion platform |
| inventory-service | Fulfillment | Stock levels and stock reservations |
| returns-service | Fulfillment | Customer returns and return processing |
| pricing-service | Commerce | Prices and quotes |
| payment-service | Commerce | Payment processing through the PayNimbus gateway |
| billing-service | Commerce | Invoicing and financial records, with export to LedgerOne |
| shipping-service | Logistics | Shipments, labels and tracking for Orion callers |
| carrier-gateway | Logistics | Integration with the SwiftShip carrier API |
| notification-service | Platform | Outbound customer and internal notifications |
| identity-service | Platform | Authentication and service to service identity |
| reporting-service | Data | Operational and business reporting |
| customer-service | CRM | Customer records, synchronised with Relatia |

## Service notes

### order-service (Fulfillment)

The heart of Orion. order-service holds the order record and its status as the order moves from placement through fulfilment. Most other services either feed it or react to it. Changes here tend to have wide impact, so the Fulfillment team asks for an architecture review on anything that alters the order model.

### inventory-service (Fulfillment)

Tracks what stock is available and where, and handles reservations so the same unit is not promised twice. Sits naturally with order-service under Fulfillment, since most of its traffic comes from order flows.

### returns-service (Fulfillment)

**returns-service is owned by Fulfillment.** It manages customer returns: recording the return request, tracking the returned items back into the warehouse, and coordinating with downstream services so that stock and financial records reflect the return. Fulfillment owns it because returns are, operationally, a reverse fulfilment flow and the team already owns the stock side of the picture.

### pricing-service (Commerce)

Calculates prices and quotes. Commerce owns everything that touches money on the way in, and pricing is the first step of that.

### payment-service (Commerce)

The only Orion service that talks to PayNimbus, Northwind's payment gateway. Responsible for authorising and capturing payments and for handling failed payments. See the payment runbooks for incident procedures.

### billing-service (Commerce)

Produces invoices and financial records and exports them to LedgerOne, Northwind's ERP. Commerce owns it to keep the money trail within one team.

### shipping-service (Logistics)

Serves the internal shipping API used by the rest of Orion for creating shipments, generating labels and tracking parcels.

### carrier-gateway (Logistics)

Encapsulates the integration with SwiftShip, the carrier API. Keeping it separate from shipping-service lets the Logistics team change carrier specifics without touching the internal shipping contract.

### notification-service (Platform)

A shared capability that other services use to send notifications. Platform owns it because it is used by nearly every domain and has no single business owner.

### identity-service (Platform)

Issues and validates identities and tokens for users and for service to service calls. Like notification-service, it is cross cutting infrastructure and sits with Platform.

### reporting-service (Data)

Builds operational and business reporting from Orion events and data. Owned by the Data team.

### customer-service (CRM)

Holds customer records for Orion and keeps them synchronised with Relatia, the CRM system. Owned by the CRM team, which also owns the relationship with that vendor.

## Shared infrastructure

Services communicate asynchronously over the platform event bus as well as through direct APIs. Event bus operations are a platform concern rather than belonging to any single service listed above.

## How to change ownership

1. The current and proposed owning teams agree the move in principle.
2. The change is raised at architecture review with a short note covering on-call handover, open incidents and roadmap items.
3. Once accepted, the paging tool and repository permissions are updated.
4. The change is recorded in the next edition of this catalog.

## Questions

Questions about this catalog go to architecture review. Questions about a specific service go to its owning team.
