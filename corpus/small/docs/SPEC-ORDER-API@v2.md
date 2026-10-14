---
Document ID: SPEC-ORDER-API
Version: v2
Title: Order API v2
Date: 2024-11-18
Status: Current
---

# Order API v2

This document specifies version 2 of the Orion Order API, the interface through which internal channels and partner integrations create, retrieve and cancel orders on the Orion order management platform. The API is served by order-service.

> **New integrations must use v2.** Version 1 of the Order API remains documented in SPEC-ORDER-API v1 for existing clients only. Do not start new work against v1.

## 1. Why a v2

The short version: v1 could not protect clients from themselves when the network misbehaved. If a client sent a create request, timed out waiting for a response, and retried, there was no way for the server to know the second request was the same order. Both could succeed. ADR-007 records the decision to introduce idempotency as a first class requirement in v2 and to deprecate v1 once v2 is available.

Beyond idempotency, v2 also tidies up a few things that had accumulated in v1: more consistent error bodies, explicit rate limit headers, and a cleaner separation between the order resource and its status history.

## 2. Conventions

- All requests and responses use JSON with UTF-8 encoding.
- All endpoints are under the `/v2` path prefix.
- Field names are `camelCase`.
- Timestamps are ISO 8601 strings in UTC.
- Monetary amounts are represented as an object with an amount string and a currency code, never as floating point numbers.
- Unknown fields in requests are rejected rather than ignored, so typos surface early.

Authentication follows the platform's standard service and partner authentication scheme. Requests without valid credentials receive `401 Unauthorized`.

## 3. Idempotency

### 3.1 The Idempotency-Key header

Order creation requires the `Idempotency-Key` header. A create request without it is rejected with `400 Bad Request` and an error code of `idempotency_key_missing`. There is no opt-out.

The key is an opaque string chosen by the client. We recommend a randomly generated UUID per logical order attempt. What matters is the rule: **generate one key per order the user intends to place, and reuse that same key for every retry of that order.** Generating a fresh key on retry defeats the purpose entirely.

### 3.2 Retention window and replay behaviour

Idempotency keys are retained for **24 hours** from the first request that used them.

Within that 24 hour window:

- If a request arrives with a key that has already been used for a completed create, the API does **not** create a new order. It returns the original order, with the same order ID and the same response body as the original successful response.
- If the original request with that key is still being processed, the API returns `409 Conflict` with the error code `idempotency_request_in_progress`. Clients should back off and retry with the same key.
- If the key is reused with a request body that differs from the original, the API returns `422 Unprocessable Entity` with the error code `idempotency_key_reused`. This almost always indicates a client bug where keys are being shared across different orders.

After the 24 hour window the key is forgotten. A request using an expired key is treated as a brand new order. In practice clients should never be retrying the same order a day later; if they are, something upstream needs attention.

### 3.3 Scope of keys

Keys are scoped to the authenticated client. Two different clients using the same key string do not collide.

Idempotency applies to order creation. Read operations are naturally safe to retry. Cancellation is idempotent by nature (cancelling an already cancelled order returns the cancelled order), so it does not require the header, though clients may send it.

## 4. Rate limiting

The rate limit is **200 requests per minute per client**, counted across all v2 endpoints for that client.

Every response includes headers describing the client's current position:

| Header | Meaning |
|---|---|
| `X-RateLimit-Limit` | The limit applied to this client |
| `X-RateLimit-Remaining` | Requests left in the current window |
| `X-RateLimit-Reset` | When the current window resets, as a UTC timestamp |

When the limit is exceeded the API returns `429 Too Many Requests` with a `Retry-After` header. Clients should honour `Retry-After` rather than retrying immediately. Combined with idempotency keys, a rate limited create is always safe to retry later with the same key.

## 5. Endpoints

### 5.1 Create an order

`POST /v2/orders`

Headers:

- `Idempotency-Key` (required)
- `Content-Type: application/json`

Request body (abridged):

```json
{
  "customerId": "string",
  "channel": "string",
  "lines": [
    {
      "sku": "string",
      "quantity": 1
    }
  ],
  "shippingAddress": { "...": "..." },
  "billingAddress": { "...": "..." },
  "clientReference": "string"
}
```

`clientReference` is an optional free text field for the caller's own reference. It is stored and echoed back but has no effect on idempotency. Do not use it as a substitute for the `Idempotency-Key` header.

Responses:

- `201 Created` with the full order resource on success.
- `200 OK` with the original order resource when the request is a replay of a completed create within the idempotency window. The body is identical to the original `201` body so that clients do not need special handling.
- `400`, `409`, `422`, `429` as described in sections 3, 4 and 7.

Order creation involves several downstream checks inside Orion. Clients should treat the call as a single operation and should not make assumptions about what happens internally or in which order. A successful response means the order has been accepted; it does not mean it has shipped.

### 5.2 Retrieve an order

`GET /v2/orders/{orderId}`

Returns the current state of the order, including lines, addresses, current status and a summary of the status history. Returns `404 Not Found` if the order does not exist or is not visible to the calling client.

### 5.3 List orders

`GET /v2/orders`

Supports filtering by customer, status and creation time range. Results are paginated using an opaque cursor returned in the response. Clients pass the cursor back to fetch the next page. Do not try to construct or parse cursors.

### 5.4 Cancel an order

`POST /v2/orders/{orderId}/cancel`

Requests cancellation of an order. Cancellation is owned by order-service, which decides whether the order is still in a cancellable state. If it is not (for example it has already been handed over for shipping), the API returns `409 Conflict` with the error code `order_not_cancellable`.

An optional `reason` field may be supplied for reporting purposes.

## 6. Order statuses

Orders move through a set of statuses. Clients should treat the status as an enumerated string and must tolerate new values being added in future releases without breaking. The core statuses clients will see today are:

- `accepted`: the order has been created and accepted by Orion.
- `in_fulfillment`: the order is being picked, packed or prepared.
- `shipped`: the order has been handed to a carrier.
- `delivered`: the carrier has confirmed delivery.
- `cancelled`: the order was cancelled before shipping.

## 7. Errors

All error responses share one shape:

```json
{
  "error": {
    "code": "string",
    "message": "human readable description",
    "details": {}
  }
}
```

The `code` field is stable and safe to branch on. The `message` field is for humans and may change wording at any time. Do not parse it. Server side errors use the same shape. A server error on create is exactly the situation idempotency exists for: retry with the same key.

## 8. Client guidance

A few things we have seen go wrong in early integrations:

1. **Generating the key inside the retry loop.** The key must be generated once, before the first attempt, and reused on every retry.
2. **Treating `200` on create as an error.** A `200` on create is a successful replay. It is a good outcome.
3. **Retrying `422 idempotency_key_reused`.** This is a client bug, not a transient error. Retrying will never succeed.

## 9. Migration from v1

Existing v1 clients should plan their move to v2. The main changes are:

- Add `Idempotency-Key` to every create call and fix retry logic accordingly.
- Update error handling to the new error shape.
- Use the `/v2` path prefix.
- Switch from v1's combined status field to the v2 statuses.

Deprecation and sunset details for v1 are maintained in SPEC-ORDER-API v1.

## 10. References

- ADR-007: Order API versioning and idempotency
- SPEC-ORDER-API v1: Order API v1
