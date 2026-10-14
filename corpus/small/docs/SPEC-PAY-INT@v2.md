# PayNimbus integration

**Document ID:** SPEC-PAY-INT
**Version:** v2
**Title:** PayNimbus integration
**Date:** 2025-07-14
**Status:** Current
**Supersedes:** SPEC-PAY-INT v1

---

## Summary of changes from v1

The only behavioural change in this version is the client timeout. **payment-service now uses an 8 second timeout for PayNimbus calls.** **The timeout was reduced from 10 seconds to align with the PayNimbus contract response guarantee of 8 seconds at p99.** The rest of the document has been reorganised and clarified, but the integration contract is otherwise unchanged.

## 1. Scope

This specification covers how payment-service, part of the Orion order management platform, integrates with PayNimbus, our payment gateway. It describes the operations payment-service uses, how requests and responses are handled, how timeouts and errors are treated, and the operational expectations on both sides.

It does not cover:

- How other Orion services interact with payment-service. That is defined by payment-service's own API documentation.
- Commercial terms of the PayNimbus agreement, beyond the response guarantee that directly drives our timeout setting.
- Card data handling inside PayNimbus, which is their responsibility.

## 2. Roles

- **payment-service** is the only Orion component permitted to talk to PayNimbus. No other service holds PayNimbus credentials or calls PayNimbus directly. This keeps payment logic, credential handling and reconciliation in one place.
- **PayNimbus** authorizes, captures, voids and refunds payments on our behalf and returns a result for each operation.
- The **payment-service maintainers** own the integration on the Orion side and are the escalation point for issues.

## 3. Operations

payment-service uses the following PayNimbus operations:

| Operation | Purpose |
|---|---|
| Authorize | Reserve funds against a payment method for an order. |
| Capture | Collect previously authorized funds. |
| Void | Release an authorization that will not be captured. |
| Refund | Return captured funds, fully or partially. |
| Status lookup | Retrieve the current state of a payment by its PayNimbus reference. |

Every request from payment-service carries a client generated reference that ties the PayNimbus operation back to the Orion payment record. PayNimbus echoes this reference in its responses, and payment-service stores both its own reference and the PayNimbus reference so that either side can trace a transaction.

## 4. Authentication and credentials

payment-service authenticates to PayNimbus with credentials issued by PayNimbus. These credentials are stored and rotated in line with POL-SEC-01. They are never logged, never placed in configuration files in source control and never shared with other services.

## 5. Timeouts

### 5.1 Current setting

payment-service applies an **8 second** timeout to every PayNimbus call. The timer covers the full request, from sending to receiving a complete response.

### 5.2 Why 8 seconds

In v1 the timeout was 10 seconds. That value was chosen early, before the PayNimbus contract was finalised, and was simply a generous round number.

The PayNimbus contract now gives a response guarantee of 8 seconds at p99. Keeping our timeout above the contractual guarantee had two downsides:

- When PayNimbus was degraded, payment-service kept waiting on calls for longer than the contract says a healthy response should take, which consumed resources and delayed the moment a likely failure was recognised and handled.
- It blurred the line between "PayNimbus was slow but within contract" and "PayNimbus breached its guarantee". With the timeout aligned to the guarantee, a timeout on our side corresponds directly to a response that falls outside what the contract promises, which makes conversations with the vendor much simpler.

The timeout was therefore reduced from 10 seconds to 8 seconds so that it aligns with the contract.

### 5.3 Changing the timeout

The timeout is a configuration value, but it should not be changed casually. Any change must be reflected in a new version of this specification with the reasoning, and should be checked against the current PayNimbus contract terms first.

## 6. Error handling

PayNimbus responses fall into three groups, and payment-service treats them differently.

**Definitive declines.** PayNimbus has processed the request and declined it, for example due to insufficient funds or a rejected payment method. These are business outcomes, not errors. payment-service records the decline and returns it to the caller. They are never retried.

**Client errors.** The request was malformed or failed validation at PayNimbus. These indicate a bug on our side. payment-service logs them with full context (excluding sensitive payment data) and raises an alert. They are never retried, because retrying the same bad request will not help.

**Transient failures and timeouts.** Network failures, server errors from PayNimbus, and requests that exceed the 8 second timeout. For these, the outcome is unknown: PayNimbus may or may not have processed the operation.

For unknown outcomes payment-service must not assume failure. Before any retry, it performs a status lookup using the client generated reference to discover whether the original operation succeeded. Only if PayNimbus confirms that no operation exists for that reference is the operation attempted again. This prevents double authorizations and double refunds, which are far more expensive to unwind than a short delay.

Retry handling for payments that cannot be resolved immediately is managed through payment-service's retry mechanism, described in payment-service's own operational documentation.

## 7. Logging and observability

For every PayNimbus call payment-service records:

- The operation type.
- Both the Orion and PayNimbus references.
- The outcome category (success, decline, client error, transient failure, timeout).
- The elapsed time.

Elapsed time is tracked as a latency distribution and compared against the contractual guarantee. A dashboard shows the share of calls that hit the timeout, which is the clearest single signal of PayNimbus health from our side. Sensitive payment data is never written to logs.

## 8. Operational expectations

- Sustained timeouts or elevated transient failures page the payment-service on-call engineer, who checks the PayNimbus status channel and opens a case with PayNimbus support if the problem is on their side.
- Breaches of the response guarantee should be recorded with timestamps and references so they can be raised with PayNimbus through the vendor relationship.
- Planned PayNimbus maintenance is communicated by PayNimbus in advance and should be relayed to the payment-service maintainers so that alerts can be interpreted correctly during the window.

## 9. Related documents

- SPEC-PAY-INT v1 (superseded by this document).
- POL-SEC-01 for credential storage and rotation.
