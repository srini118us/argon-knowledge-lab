| | |
|---|---|
| **Document ID** | CT-SWIFT-2024 |
| **Version** | A1 |
| **Title** | SwiftShip agreement, Amendment 1 |
| **Date** | 2025-09-15 |
| **Status** | Current |
| **Supersedes** | CT-SWIFT-2024 v1 for the terms below |

# SwiftShip agreement, Amendment 1

*Internal summary of the executed amendment between Northwind Logistics and SwiftShip (carrier API). This summary is maintained by the vendor management function for engineering and operations readers. In case of any conflict, the signed amendment governs.*

## 1. Purpose of this amendment

The original SwiftShip agreement (CT-SWIFT-2024 v1) covers Northwind Logistics' use of the SwiftShip carrier API for label creation, rate lookups, tracking and related carrier operations used by the Orion order management platform.

Since that agreement was signed, Northwind's shipment volume and operating hours have changed. Two terms in particular became a source of friction for the engineering and operations teams:

1. The request rate allowed against the SwiftShip API, which the platform was coming up against during busy periods.
2. The vendor support coverage, which did not match the hours during which Northwind actually ships and therefore needs help.

This amendment changes those two terms and nothing else.

## 2. Amended terms

### 2.1 API rate limit

**The rate limit for Northwind Logistics' access to the SwiftShip API is raised to 120 requests per second.**

This replaces the rate limit stated in CT-SWIFT-2024 v1. The new limit applies across Northwind's account as a whole, not per calling service, so engineering teams should continue to treat it as a shared budget.

### 2.2 Vendor support hours

**SwiftShip vendor support is now available 24x7.**

This replaces the support hours stated in CT-SWIFT-2024 v1. Northwind staff may raise support requests through the existing support channels at any time of day, on any day.

## 3. Unchanged terms

**All other terms of the original agreement are unchanged.** This includes, without limitation, pricing, term and renewal, liability, data handling, confidentiality, and any service commitments set out in CT-SWIFT-2024 v1. Readers looking for any of those terms should consult the original agreement, not this amendment.

## 4. What this means for engineering

- **Throttling configuration.** Any client side throttling or rate limiting that was tuned to the old limit should be reviewed against the new figure of 120 requests per second. Do not simply set client limits equal to the contractual ceiling; leave headroom so that retries and bursts from multiple services do not push Northwind over the limit.
- **Alerting.** If there is alerting on rate limit rejections from SwiftShip, thresholds and runbook text that reference the old limit should be updated.
- **Capacity planning.** The higher limit removes a known bottleneck for peak periods. It does not remove the need for sensible backoff and retry behaviour when SwiftShip returns transient errors.

## 5. What this means for operations and on-call

- With support available 24x7, the on-call engineer no longer needs to wait for SwiftShip business hours before escalating a carrier side problem. If an incident points to SwiftShip, open a support request with the vendor as soon as the evidence supports it.
- When opening a request, include timestamps, the affected operation (label, tracking, rates, cancellation), sample request identifiers and any error payloads returned by SwiftShip. Good evidence shortens the vendor's investigation.
- Escalation steps in internal runbooks that mention "wait until vendor hours" should be removed or rewritten.

## 6. Change history

| Version | Summary |
|---|---|
| v1 | Original SwiftShip agreement |
| A1 | Raises rate limit to 120 requests per second; vendor support becomes 24x7; all other terms unchanged |

## 7. Contacts

Questions about the commercial terms go to the vendor management function. Questions about how Orion services consume the SwiftShip API go to the team that owns the carrier integration, as listed in the current Orion service catalog.
