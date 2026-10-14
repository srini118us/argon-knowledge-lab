---
Document ID: SPEC-SHIP-API
Version: v2
Title: Shipping API v2
Date: 2025-03-10
Status: Current
---

# Shipping API v2

## 1. Overview

The Shipping API v2 is the internal interface that Orion services use to create shipments, request shipping labels, track parcels and cancel shipments that have not yet been handed to a carrier.

**Shipping API v2 is served by shipping-service.** Callers should treat shipping-service as the single entry point for anything shipment related. How shipping-service fulfils a request behind the API, including how it works with carrier integrations, is an implementation detail and is intentionally not part of this contract. Callers must not depend on it.

### 1.1 Audience

- Engineers on services that need to create or inspect shipments (most commonly order fulfilment flows and returns flows).
- On-call engineers diagnosing label or tracking issues.
- Anyone writing contract tests against shipping-service.

### 1.2 Design principles

- **Resource oriented.** Shipments are the core resource. Labels and tracking are sub-resources of a shipment.
- **Idempotent writes.** Every create or cancel call accepts an idempotency key so that retries are safe.
- **Explicit state.** A shipment always has exactly one status, and transitions are documented below.
- **Additive evolution.** New optional fields may be added to responses at any time. Clients must ignore fields they do not recognise.

## 2. Service level targets

| Target | Value | Notes |
|---|---|---|
| Label generation latency | **2 seconds at p95** | Internal target, measured at shipping-service from request received to label returned |

The label generation target is an **internal** target used by the owning team to track health and drive alerting. It is not a contractual commitment to any external party. Most of the time spent generating a label is waiting on the carrier, so consumers should still design for the occasional slow label and use the asynchronous status checks described in section 5 rather than holding user facing requests open.

## 3. Conventions

- **Transport:** HTTPS, JSON request and response bodies, UTF-8.
- **Authentication:** service to service tokens issued by identity-service. Requests without a valid token are rejected.
- **Idempotency:** `Idempotency-Key` header on all `POST` requests. Replaying the same key with the same body returns the original result. Replaying the same key with a different body is rejected as a conflict.
- **Correlation:** callers should pass a `X-Correlation-Id` header. shipping-service echoes it in responses and logs it, which makes cross service debugging much less painful.
- **Timestamps:** ISO 8601 in UTC.
- **Identifiers:** opaque strings. Do not parse them.

### 3.1 Errors

Errors use a consistent envelope:

```json
{
  "error": {
    "code": "ADDRESS_INVALID",
    "message": "Destination postal code could not be validated",
    "details": { "field": "destination.postalCode" },
    "correlationId": "..."
  }
}
```

Common error codes:

| Code | Meaning | Retry? |
|---|---|---|
| `VALIDATION_FAILED` | Request body failed schema validation | No, fix the request |
| `ADDRESS_INVALID` | Address could not be validated | No |
| `SHIPMENT_NOT_FOUND` | Unknown shipment ID | No |
| `INVALID_STATE` | Operation not allowed in the shipment's current status | No |
| `IDEMPOTENCY_CONFLICT` | Same key, different body | No |
| `CARRIER_UNAVAILABLE` | Carrier could not be reached or rejected the request transiently | Yes, with backoff |
| `INTERNAL_ERROR` | Unexpected failure in shipping-service | Yes, with backoff |

## 4. Resources and endpoints

### 4.1 Create shipment

`POST /v2/shipments`

Creates a shipment record for an order. Creating a shipment does not by itself generate a label.

Request body (abridged):

```json
{
  "orderId": "string",
  "origin": { "warehouseId": "string" },
  "destination": {
    "name": "string",
    "line1": "string",
    "line2": "string",
    "city": "string",
    "region": "string",
    "postalCode": "string",
    "country": "string"
  },
  "parcels": [
    { "weight": { "value": 0, "unit": "kg" },
      "dimensions": { "length": 0, "width": 0, "height": 0, "unit": "cm" } }
  ],
  "serviceLevel": "STANDARD | EXPRESS",
  "reference": "string"
}
```

Response: the shipment resource with status `CREATED`.

### 4.2 Get shipment

`GET /v2/shipments/{shipmentId}`

Returns the shipment, its parcels, current status, and links to its label and tracking sub-resources once they exist.

### 4.3 Generate label

`POST /v2/shipments/{shipmentId}/label`

Requests a shipping label for an existing shipment. On success the response includes the label format, a download reference and the carrier tracking number. This is the operation covered by the **2 seconds at p95** internal latency target.

If label generation cannot complete within the request, shipping-service returns the shipment in `LABEL_PENDING` and the caller should poll the shipment or label resource. Callers must not resubmit with a new idempotency key while a label is pending, as that can produce duplicate labels.

### 4.4 Get label

`GET /v2/shipments/{shipmentId}/label`

Returns label metadata and the download reference. Returns `SHIPMENT_NOT_FOUND` if the shipment does not exist and `INVALID_STATE` if no label has been generated yet.

### 4.5 Tracking

`GET /v2/shipments/{shipmentId}/tracking`

Returns the list of tracking events known to shipping-service, newest first, each with a timestamp, a normalised event type and the carrier's own description. The normalised types are `LABEL_CREATED`, `PICKED_UP`, `IN_TRANSIT`, `OUT_FOR_DELIVERY`, `DELIVERED`, `EXCEPTION`.

### 4.6 Cancel shipment

`POST /v2/shipments/{shipmentId}/cancel`

Cancels a shipment that has not yet been picked up. Cancelling a shipment with a label voids the label with the carrier. Cancelling after pickup returns `INVALID_STATE`; use the returns flow instead.

## 5. Shipment lifecycle

```
CREATED -> LABEL_PENDING -> LABELLED -> IN_TRANSIT -> DELIVERED
   |             |              |
   +-------------+--------------+--> CANCELLED
                                IN_TRANSIT -> EXCEPTION
```

- `CREATED`: shipment record exists, no label yet.
- `LABEL_PENDING`: label requested, waiting on the carrier.
- `LABELLED`: label available; awaiting pickup.
- `IN_TRANSIT`: carrier has the parcel.
- `DELIVERED`: terminal.
- `EXCEPTION`: carrier reported a problem. May recover to `IN_TRANSIT`.
- `CANCELLED`: terminal.

## 6. Guidance for consumers

- Generate labels as late as is practical in the fulfilment flow, since cancelling a labelled shipment involves a round trip to the carrier.
- Do not block a customer facing request on label generation. Request the label, return, and let the status update flow through.
- Retry only the error codes marked retryable, with exponential backoff and jitter, and always reuse the original idempotency key.
- Log the correlation ID on your side. When raising an issue with the owning team, include it.

## 7. Change policy

Changes within v2 are additive only. Removing a field, changing a field's meaning, or changing a status transition requires a new major version and a migration plan agreed with consuming teams.
