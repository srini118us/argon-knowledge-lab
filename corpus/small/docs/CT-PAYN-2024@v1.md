Document ID: CT-PAYN-2024
Version: v1
Title: PayNimbus payment services agreement
Date: 2024-06-01
Status: Current

---

# PayNimbus payment services agreement: contract summary

*Prepared by Procurement with input from the engineering and finance teams. This is a working summary for people who need to know what we can expect from PayNimbus and what we owe them. It is not the contract. If anything here conflicts with the signed agreement, the signed agreement wins, and please tell Procurement so this page can be corrected.*

## At a glance

| Term | What the agreement says |
|---|---|
| Vendor | PayNimbus |
| Service | Payment gateway: authorisation, capture, void, refund and related payment processing for Northwind Logistics |
| Availability SLA | **99.95%** |
| Response guarantee | **8 seconds at p99** |
| Settlement period | **T+2** |
| Fee dispute window | **60 days** |

The rest of this page explains what each of these means in practice and who at Northwind is expected to act on them.

## Background

Northwind Logistics takes customer payments through the Orion order management platform. Within Orion, payment-service is the single component that talks to PayNimbus. Before this agreement was signed, the commercial terms with PayNimbus were thin on service commitments, which made it hard for engineering to set sensible timeouts and hard for finance to plan cash flow. The negotiation that produced this agreement was driven largely by those two needs: a clear performance commitment that engineering could design against, and a clear settlement schedule that finance could plan around.

## Service levels

### Availability

PayNimbus commits to an **availability SLA of 99.95%** for the payment API used by Northwind. Availability is measured by PayNimbus according to the definitions in the agreement, which exclude scheduled maintenance that has been notified in advance.

Practical notes:

- A 99.95% commitment is strong, but it is not zero downtime. Orion has to be built on the assumption that PayNimbus will sometimes be unavailable. The payment failures runbook covers what the on-call engineer does when that happens.
- If we believe PayNimbus has missed the SLA in a given measurement period, the claim has to be raised with PayNimbus by Procurement, using our own incident records as supporting evidence. Engineering should make sure incident timelines for PayNimbus related outages are accurate, because they may end up being used in a service credit discussion.

### Response guarantee

PayNimbus guarantees a **response time of 8 seconds at p99** for payment API calls. In other words, 99 out of every 100 calls should receive a response within 8 seconds.

This is the number engineering cares about most. It gives payment-service a defensible upper bound for its PayNimbus timeout. A client timeout well above the guarantee means tolerating calls that are already outside what the vendor has committed to; a timeout well below it risks abandoning calls that PayNimbus would have answered within its commitment. The integration specification for PayNimbus (SPEC-PAY-INT) is the place where the timeout actually used by payment-service is documented, and anyone revisiting that value should start from this guarantee.

## Money

### Settlement period

Funds captured through PayNimbus settle to Northwind on **T+2**, meaning two business days after the transaction date. Finance uses this to forecast incoming cash. Delays beyond T+2 should be raised with PayNimbus through the account contact named in the agreement; finance owns that conversation, not engineering.

### Fees and disputes

PayNimbus charges transaction fees according to the fee schedule attached to the agreement. That schedule is commercially sensitive and is deliberately not reproduced here; finance and Procurement have access to it.

The **fee dispute window is 60 days**. If finance believes PayNimbus has charged a fee incorrectly, the dispute has to be raised within 60 days or we lose the right to contest it. In practice that means invoice reconciliation needs to happen promptly every cycle, not quarterly. Finance has set up a reminder for this; if the reconciliation process changes, check the reminder still lines up.

Note that the fee dispute window is about PayNimbus's fees to us. It is separate from customer chargebacks, which follow card network rules and are handled through the PayNimbus dispute process described in their merchant documentation.

## Responsibilities on our side

The agreement places some obligations on Northwind as well:

- **Credentials.** We must protect the API credentials PayNimbus issues to us. On our side these live in HashiCorp Vault and are only accessible to payment-service, in line with POL-SEC-01.
- **Card data.** We must handle card data in line with the data protection obligations set out in the agreement.
- **Incident notification.** If we suspect a compromise of our PayNimbus credentials or integration, we must notify PayNimbus without undue delay. The security on-call coordinates this.
- **Correct use of the API.** We are expected to follow PayNimbus's published integration guidelines, including their guidance on retries. Hammering the API during an outage is both bad practice and potentially a breach of those guidelines.

## No secondary provider

There is no second payment gateway behind PayNimbus. This agreement does not include any failover arrangement, and Orion does not route payments to another provider if PayNimbus is down. That was a conscious choice when the agreement was negotiated, trading resilience for simplicity. It is the reason the availability and response commitments above matter so much.

## Who to contact

| Topic | Northwind owner |
|---|---|
| Commercial terms, SLA claims | Procurement |
| Settlement and fee disputes | Finance |
| Technical integration and incidents | The engineer on call for payment-service |
| Suspected credential compromise | Security on-call |

## Change history

This is the first version of the summary, written when the agreement came into effect. Any amendment to the agreement should produce a new version of this page rather than an in place edit, so that people reading older incident reports can see what terms applied at the time.
