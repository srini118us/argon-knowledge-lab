**Document ID:** SPEC-PAY-INT
**Version:** v1
**Title:** PayNimbus integration
**Date:** 2024-05-06
**Status:** Superseded
**Superseded by:** SPEC-PAY-INT v2

> **Status: Superseded by version v2.** This page is kept for history and for anyone reading old incident reports. Do not build against it. Use SPEC-PAY-INT v2 for current behaviour.

# PayNimbus integration specification

## 1. Purpose and scope

This specification describes how the Orion order management platform integrates with PayNimbus, the payment gateway Northwind Logistics uses to authorise and capture customer payments. It covers the boundary between payment-service and PayNimbus: which operations we use, how we handle errors, what we log and what the timeout behaviour is.

It does not cover how order-service or any other Orion service interacts with payment-service. Those are internal contracts documented elsewhere. It also does not cover the commercial terms with PayNimbus; see the PayNimbus contract summary for those.

## 2. Ownership of the boundary

payment-service is the only Orion component allowed to talk to PayNimbus. No other service holds PayNimbus credentials, and no other service should ever construct a PayNimbus request, even for read only lookups. Funnelling everything through payment-service keeps the credential surface small, keeps all payment logging in one place and means that a change on the PayNimbus side only has to be absorbed in one codebase.

## 3. Operations used

payment-service uses a small subset of the PayNimbus API:

| Operation | Used for |
|---|---|
| Authorise | Placing a hold on the customer's payment method for an order |
| Capture | Collecting funds against an existing authorisation |
| Void | Releasing an authorisation that will not be captured |
| Refund | Returning funds for a captured payment |
| Status lookup | Checking the current state of a payment when our own record is unclear |

Anything else PayNimbus offers (stored payment methods, reporting endpoints and so on) is out of scope for v1.

## 4. Request handling

### 4.1 Timeout

**payment-service uses a 10 second timeout for PayNimbus calls.** The timeout applies to every operation in the table above. If PayNimbus has not responded within 10 seconds, payment-service treats the outcome of that call as unknown.

The value was chosen when the integration was first built, based on the behaviour the team observed in testing and on a wish to stay generous rather than give up on slow but successful payments. It is a single value for all operations; we did not see enough difference between operations to justify separate settings.

### 4.2 Unknown outcomes

A timeout does not mean the payment failed. PayNimbus may have processed the request and simply been slow to reply. For that reason payment-service never treats a timeout as a decline. Instead it marks the payment as pending verification and uses the status lookup operation to find out what actually happened before taking any further action. Only once the real state is known does payment-service report success or failure to its caller.

This matters most for capture and refund, where a blind retry could move money twice.

### 4.3 Error classification

payment-service sorts PayNimbus responses into three groups:

- **Success.** Recorded and returned to the caller.
- **Definitive failure.** For example, a card decline or an invalid request. Recorded and returned to the caller. These are not retried, because retrying a decline does not change the answer.
- **Transient or unknown.** Timeouts, connection failures and server side errors from PayNimbus. These go through the unknown outcome handling in 4.2.

## 5. Security

PayNimbus credentials are stored in HashiCorp Vault in line with the platform security policy, POL-SEC-01. payment-service fetches them at startup and on rotation; they are never written to configuration files, logs or environment dumps.

Raw card data must not be stored by payment-service. The integration works with PayNimbus payment references, and anything more sensitive is out of scope for this specification.

## 6. Logging and audit

Every PayNimbus call is logged with the operation, the Orion order reference, the PayNimbus payment reference, the outcome classification and the elapsed time. Request and response bodies are not logged in full. The elapsed time field is what the team uses to see how close calls are running to the timeout, so please keep it in any future log format change.

## 7. Testing

The integration is exercised in three ways:

1. Unit tests in payment-service with a stubbed PayNimbus client, covering each classification path in section 4.3.
2. Contract tests against the PayNimbus sandbox, run before each payment-service release.
3. A manual check by the engineer releasing payment-service that a sandbox authorise and void round trip succeeds.

Timeout behaviour is tested with a stub that deliberately delays its response beyond the configured timeout.

## 8. Open questions (at time of writing)

- Whether a single timeout for all operations is the right long term choice, or whether capture and refund should be treated differently.
- Whether the timeout value should be revisited once the contract terms with PayNimbus are finalised.

These questions were picked up in the next revision of this specification.
