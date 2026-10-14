---
Document ID: SPEC-ORDER-API
Version: v1
Title: Order API v1
Date: 2024-03-04
Status: Deprecated
---

# Order API v1

> **Deprecation notice.** Order API v1 is deprecated. **Sunset date: 2025-12-31; after this date v1 requests are rejected.** Integrators still calling v1 should plan their move to Order API v2 well ahead of the sunset date. This document is kept for reference while the remaining clients migrate.

## 1. Purpose

Order API v1 is the original public interface to order-service, the component of the Orion order management platform that accepts, stores and tracks customer orders. It was designed for a small number of internal clients and a few early partner integrations, and it reflects the assumptions of that time: low traffic, trusted callers, and simple order shapes.

This specification describes the resources, request and response conventions, error behaviour and known limitations of v1. It does not describe how order-service processes an order internally; that is out of scope for an API contract and is covered by the service's own design documentation.

## 2. Audience

- Engineers maintaining clients that still call v1.
- Support engineers investigating historical integration issues.
- Anyone planning the migration of a v1 client to v2.

## 3. Conventions

- All requests and responses use JSON.
- Field names are snake_case.
- Timestamps are ISO 8601 strings in UTC.
- Monetary amounts are expressed as a decimal string together with a currency code, never as floating point numbers.
- Requests must carry a valid bearer token. Unauthenticated requests are rejected.
- The API version is part of the path, for example `/v1/orders`.

## 4. Resources

### 4.1 Orders

An order represents a customer's request to buy one or more items. The order resource contains:

| Field | Type | Notes |
|---|---|---|
| order_id | string | Assigned by order-service on creation. |
| customer_id | string | Reference to the customer record. |
| lines | array | One entry per item ordered. |
| shipping_address | object | Free form address structure in v1. |
| status | string | See section 5. |
| created_at | timestamp | Set by the server. |
| updated_at | timestamp | Set by the server. |

Each entry in `lines` carries a product reference, a quantity and the unit price as quoted to the customer.

### 4.2 Endpoints

**Create an order**

`POST /v1/orders`

Accepts an order body without `order_id`, `status` or timestamps. On success, returns the full order resource including the server assigned `order_id`.

**Retrieve an order**

`GET /v1/orders/{order_id}`

Returns the order resource. If the order does not exist or the caller is not permitted to see it, the request is rejected with a not found error; v1 deliberately does not distinguish between the two cases.

**List orders for a customer**

`GET /v1/orders?customer_id={customer_id}`

Returns orders for a single customer, newest first. Pagination uses an opaque cursor returned in the response; clients pass it back unchanged to fetch the next page.

**Cancel an order**

`POST /v1/orders/{order_id}/cancel`

Requests cancellation. Whether cancellation succeeds depends on the order's current status. Orders that have progressed past the point where cancellation is possible return a conflict error describing the current status.

## 5. Order status

v1 exposes a small set of coarse statuses: received, confirmed, shipped, delivered and cancelled. These are intentionally simpler than the internal states order-service tracks. Clients should treat unknown status values as "in progress" rather than failing, because the status list was extended once during the life of v1 and some older clients broke when it happened.

## 6. Errors

Errors return a JSON body with a machine readable `error_code` and a human readable `message`. Clients should branch on `error_code`, not on `message`, since message wording has changed over time.

Broad categories:

- **Validation errors** for malformed bodies, missing required fields or invalid quantities.
- **Authentication and authorization errors** for missing, expired or insufficient tokens.
- **Not found** for unknown orders or orders the caller cannot see.
- **Conflict** for state transitions that are not allowed, such as cancelling a shipped order.
- **Server errors** for unexpected failures inside order-service.

## 7. Idempotency and retries

**v1 has no idempotency mechanism.** There is no idempotency key header and no server side deduplication of create requests.

This is the most significant limitation of v1 and one of the main reasons it is being retired. If a client sends `POST /v1/orders`, the connection drops, and the client retries, order-service has no way of knowing that the second request is a repeat of the first. The result can be two orders for the same purchase. Support has handled a steady trickle of duplicate order cases traced back to exactly this pattern, usually from clients with aggressive automatic retries in their HTTP libraries.

Guidance for clients that must remain on v1 until migration:

- Do not automatically retry `POST /v1/orders` on timeouts or connection errors.
- After an ambiguous failure, call the list endpoint for the customer and check whether the order was in fact created before trying again.
- Retrying `GET` requests is safe.
- Retrying cancel requests is generally safe, since cancelling an already cancelled order returns the current state rather than an error, but clients should still check the response.

## 8. Known limitations

Beyond the lack of idempotency, v1 has several other limitations that informed the design of its successor:

- The free form address structure makes downstream validation difficult and has caused shipping problems for international addresses.
- There is no way to partially update an order; clients must cancel and recreate.
- Error codes were added incrementally and are not fully consistent across endpoints.
- The not found response hides authorization failures, which makes debugging permission issues harder than it needs to be.

## 9. Deprecation and sunset

Order API v1 is deprecated. No new features will be added, and only critical fixes will be considered.

The sunset date is **2025-12-31**. After this date, v1 requests are rejected and clients must use Order API v2. There will be no grace period beyond the sunset date, so client owners should complete migration and verify it in production before then rather than at the last moment.

Recommended migration steps:

1. Inventory every system that calls `/v1/` paths, including scheduled jobs and partner integrations that may not be obvious.
2. Review the v2 specification and map each v1 call to its v2 equivalent.
3. Remove any client side retry logic built to work around the missing idempotency in v1, and adopt the approach the v2 specification describes.
4. Run v2 in parallel in a non production environment and compare responses.
5. Switch production traffic and monitor for errors.
6. Confirm with the order-service maintainers that no traffic from the client remains on v1.

Questions about the migration should go to the order-service maintainers through the usual support channel.
