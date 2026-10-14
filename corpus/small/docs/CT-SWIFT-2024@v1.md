**Document ID:** CT-SWIFT-2024
**Version:** v1
**Title:** SwiftShip carrier services agreement
**Date:** 2024-04-01
**Status:** Amended
**Superseded by:** CT-SWIFT-2024 Amendment 1 (for the terms that amendment changes)

---

# SwiftShip carrier services agreement: contract summary

## About this summary

This is an internal summary of the carrier services agreement between Northwind Logistics and SwiftShip. It is written for engineers, on-call staff and operations leads who need to know what the contract means for day to day work with the SwiftShip carrier API. It is not the contract. Where this summary and the signed agreement disagree, the signed agreement wins, and anyone negotiating, disputing or interpreting terms should go to the full text via vendor management.

Note that this agreement has since been amended. Read CT-SWIFT-2024 Amendment 1 alongside this summary; where the amendment changes a term, the amendment applies.

## Parties and purpose

- **Customer:** Northwind Logistics
- **Vendor:** SwiftShip

SwiftShip provides carrier services to Northwind Logistics: shipment booking, label generation, tracking updates and related carrier functions, all exposed through the SwiftShip carrier API. Within the Orion order management platform, carrier-gateway is the service that talks to the SwiftShip API on our behalf. Nothing else in Orion should be calling SwiftShip directly.

## Key operational terms at a glance

| Term | Value |
|---|---|
| SwiftShip API rate limit | 50 requests per second |
| Vendor support hours | 06:00 to 22:00 Eastern Time |

Those two numbers are the ones engineers ask about most often, and they are the ones most likely to bite during an incident. The rest of this summary explains the context around them.

## API usage

### Rate limit

The agreement sets the SwiftShip API rate limit for Northwind Logistics at **50 requests per second**. The limit applies to our account as a whole, not per service instance or per endpoint. Every carrier-gateway instance shares the same allowance.

What happens when we exceed it: SwiftShip rejects excess requests. The contract treats sustained or repeated overage as something SwiftShip may raise with us formally, so this is not just a technical concern. Exceeding the limit in a burst will cause failures; exceeding it as a pattern is a commercial conversation nobody wants to have.

Practical implications for engineering:

- Client side throttling in carrier-gateway should be configured with the account wide limit in mind, remembering that it is shared by all instances.
- Retry logic must not amplify load. A naive retry policy during a SwiftShip slowdown can easily turn a partial degradation into a full rate limit lockout. Retries need backoff, and they need a sensible cap.
- Load tests against SwiftShip environments must be coordinated with the vendor in advance and must not be pointed at production endpoints.

If we expect to need more headroom, for example because of planned volume growth, the agreement provides for the limit to be revisited by mutual agreement. That is a commercial discussion, not something to fix in configuration.

### API changes and deprecations

SwiftShip commits to giving advance notice of breaking changes to the API and to maintaining a deprecation process for older API versions. When notices arrive they go to the vendor management mailbox and are forwarded to the engineers who maintain carrier-gateway. Do not assume we will hear about changes through any other route.

### Test environment

SwiftShip provides a non-production environment for integration testing. Behaviour there is representative but not identical to production, especially for edge cases such as address validation and carrier specific surcharges. Test data must not include real customer personal data.

## Support

### Hours

Vendor support is available **06:00 to 22:00 Eastern Time**. Outside those hours there is no contracted support coverage from SwiftShip.

This matters for incident response. If carrier-gateway starts seeing SwiftShip errors overnight, on-call should assume they will not get a vendor response until support hours resume. Plan mitigations accordingly: hold and queue where possible, communicate clearly to downstream teams that label creation may be delayed, and prepare a crisp ticket so that the first SwiftShip engineer on shift can act quickly.

### How to raise an issue

Support requests go through SwiftShip's support portal, using the Northwind Logistics account. The ticket should include:

- What is failing (endpoint or operation, not just "labels are broken")
- When it started, in UTC and Eastern Time to avoid confusion
- Sample request identifiers from carrier-gateway logs
- The error responses received
- Whether we have changed anything on our side recently

Severity classification is agreed with SwiftShip when the ticket is opened. Be honest about severity; inflating it erodes trust with the vendor over time.

### Escalation

If a ticket is not getting traction, escalate through vendor management, who hold the commercial relationship and the named escalation contacts at SwiftShip. Engineers should not try to escalate directly with SwiftShip account staff.

## Data and security

- SwiftShip processes shipment data, including recipient names and delivery addresses, only for the purpose of providing carrier services to Northwind Logistics.
- SwiftShip must protect that data using appropriate technical and organisational measures and must notify us of security incidents affecting our data without undue delay.
- Credentials for the SwiftShip API are issued per environment and must be handled according to Northwind's platform security policy. They are never committed to source control or shared in chat.
- On termination, SwiftShip returns or deletes our data in line with the agreement.

## Commercial terms

Pricing, invoicing and payment terms are set out in the signed agreement and its schedules. They are deliberately not reproduced here. Questions about invoices or charges go to the vendor management and finance contacts, not to engineering.

## Term and renewal

The agreement's term, renewal mechanics and termination provisions are in the signed contract. Engineering decisions should not depend on assumptions about renewal; if a design would lock us further into SwiftShip specific behaviour, flag it in design review so that the commercial side is aware.

## What this means for Orion, in plain terms

1. carrier-gateway is our single integration point with SwiftShip. Keep it that way.
2. Treat the 50 requests per second limit as a hard ceiling shared across all instances, and design throttling and retries so we never come close in normal operation.
3. Remember that SwiftShip support is only staffed from 06:00 to 22:00 Eastern Time. Overnight incidents need a plan that does not rely on the vendor.
4. Changes to any of these terms come through amendments. Check for amendments before relying on this summary; at the time of the latest update, Amendment 1 applies.

## Related documents

- CT-SWIFT-2024 Amendment 1: SwiftShip agreement, Amendment 1
- RB-CARRIER-01: carrier-gateway incidents runbook
