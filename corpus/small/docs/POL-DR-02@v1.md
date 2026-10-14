---
Document ID: POL-DR-02
Version: v1
Title: Disaster recovery and event retention
Date: 2025-01-15
Status: Current
---

# POL-DR-02: Disaster recovery and event retention

## 1. Purpose

This policy sets the disaster recovery expectations for services on the Orion order management platform and the default retention for events on the platform's Apache Kafka event bus.

It exists so that, before anything goes wrong, everyone agrees on two questions:

- How much data can a given service afford to lose in a disaster, and how quickly must it be back?
- How long do events stay on the bus, and therefore how far back can a consumer replay?

Without a written answer, those questions get decided in the middle of an incident, by whoever happens to be awake. That is the situation this policy is meant to prevent.

## 2. Scope

This policy applies to all Orion services and to all topics on the Orion Kafka event bus. It applies to production. Non-production environments are out of scope unless a team chooses to apply it.

## 3. Definitions

- **RPO (recovery point objective):** the maximum acceptable amount of data loss, expressed as time. An RPO of 15 minutes means that after recovery, at most the last 15 minutes of changes may be lost.
- **RTO (recovery time objective):** the maximum acceptable time from the declaration of a disaster to the service being available again.
- **Tier:** the recovery class assigned to a service. The tier determines the RPO and RTO the service must be designed and tested to meet.
- **Retention:** the length of time Kafka keeps messages on a topic before they become eligible for deletion, regardless of whether they have been consumed.

## 4. Recovery tiers

### 4.1 Tier 1

Tier 1 is reserved for services whose loss directly stops Northwind Logistics from taking and fulfilling orders or taking payment.

**Tier 1 services:**

- order-service
- payment-service
- inventory-service

**Tier 1 targets:**

| Objective | Target |
|---|---|
| RPO | 15 minutes |
| RTO | 4 hours |

Tier 1 services must be deployable in the disaster recovery environment, must have data protection arrangements that can meet the 15 minute RPO, and must have a recovery procedure that has been exercised, not just written down.

### 4.2 Tier 3

Tier 3 covers services whose temporary loss is inconvenient but does not stop orders, payments or fulfilment, and whose data can be rebuilt from upstream sources.

**Tier 3 services:**

- reporting-service

**Tier 3 targets:**

| Objective | Target |
|---|---|
| RPO | 24 hours |

In a disaster, reporting-service is restored after higher tier services, and its data may be rebuilt from upstream systems and from events still retained on the bus.

### 4.3 Other services

Services not named in this policy are classified through the tiering review described in section 7. Until a service has been explicitly classified, teams must not assume it qualifies for Tier 1 treatment during a disaster.

## 5. Event retention

### 5.1 Default retention

**The default retention for Kafka topics on the Orion platform is 7 days.**

Every topic is created with the default unless an exception has been approved.

### 5.2 Why 7 days

The default balances three concerns:

- **Recovery.** Seven days is long enough for a consumer that has been down over a weekend, or that needs to reprocess after a short lived bug, to replay from the bus rather than from source systems.
- **Storage.** Retention drives disk usage on the cluster. A bounded default keeps that predictable.
- **Data exposure.** Events can contain customer and order details. Keeping them longer than necessary increases the impact of any access control mistake.

### 5.3 Exceptions

A team that needs a different retention for a specific topic must:

1. Write an architecture decision record explaining the need, the alternatives considered and the impact.
2. Get it accepted through the normal architecture review.
3. Apply the change through the standard configuration process, never by hand on the cluster.
4. Reference the decision record from the topic's configuration notes so readers of this policy are not misled.

Exceptions apply to the named topic only. An approved exception for one topic is not a precedent for others.

### 5.4 Retention is not backup

Retention on the event bus is a replay mechanism, not a backup. Services must not rely on Kafka retention alone to meet their RPO. Each service's data store must be protected in its own right.

## 6. Testing and evidence

- Tier 1 services must run a recovery exercise on a regular schedule agreed with the platform function, and record the measured recovery point and recovery time against the targets above.
- Exercises that miss a target must produce a remediation item with an owner and a due date.
- Tier 3 services must at least document and periodically walk through their rebuild procedure.

Evidence of exercises is kept with the service's operational documentation.

## 7. Tiering review

Tier assignments are reviewed when:

- A new service is introduced to Orion.
- A service's role changes materially, for example when it takes on responsibilities that put it on the order or payment path.
- An incident shows that a service's tier did not reflect its real business impact.

Proposals to change a service's tier are made through the architecture review, with the business impact explained in plain language.

## 8. Responsibilities

- **Service owners** design their services to meet their tier's targets, maintain recovery procedures, and run the required exercises.
- **The platform function** operates the Kafka event bus, enforces the default retention, and applies approved retention exceptions.
- **Incident commanders** use the tiers in this policy to decide recovery order during a disaster: Tier 1 first, Tier 3 last.

## 9. Related documents

- Architecture decision records for any approved retention exceptions.
- Service runbooks for individual recovery procedures.
