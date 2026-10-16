# ADR-028@v1: Event bus for shipment status

| Field | Value |
|---|---|
| Document | ADR-028 |
| Version | v1 |
| Status | Accepted |
| Date | 2025-06-12 |

## Context

Shipment status changes were published through point to point webhooks, which failed silently when consumers were down.

## Decision

**D1** Shipment status events are published to the internal event bus. Consumers subscribe to topics rather than receiving webhooks.

## Consequences

Consumers must handle duplicate events. This decision concerns internal consumers only and does not govern vendor integrations.

---

# ADR-031@v1: Integration gateway for all vendor traffic

| Field | Value |
|---|---|
| Document | ADR-031 |
| Version | v1 |
| Status | Accepted |
| Date | 2026-01-20 |

## Context

Teams called vendor APIs directly from their services. Credentials were duplicated, rate limits were enforced inconsistently, and there was no single place to see what data left Northwind.

## Decision

**D1** Every integration that sends data to an external vendor routes through the integration gateway, int-gw. Services must not call vendor APIs directly.

**D2** The gateway holds vendor credentials and enforces per vendor rate limits.

## Consequences

Teams lose some flexibility in client libraries. The gateway team commits to onboarding a new vendor route within five working days.

---

# ADR-033@v1: Structured logging format

| Field | Value |
|---|---|
| Document | ADR-033 |
| Version | v1 |
| Status | Accepted |
| Date | 2026-03-03 |

## Decision

**D1** All services emit JSON logs with trace ID, service name and severity fields. Free text log lines are deprecated.

## Consequences

Log parsing rules in the observability platform are simplified. Personal data must not be written to logs under any format.
