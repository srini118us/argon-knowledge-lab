Document ID: RB-CARRIER-01
Version: v1
Title: carrier-gateway incidents
Date: 2024-07-08
Status: Superseded
Superseded by: RB-CARRIER-01 v2

---

# Runbook: carrier-gateway incidents

> This version is superseded by RB-CARRIER-01 v2. It is kept for historical reference only. Use v2 for live incidents.

## What this runbook is for

carrier-gateway is the Orion service that talks to SwiftShip, our carrier API, to book shipments and retrieve labels and tracking details. When carrier-gateway is unhealthy, orders can still be placed, but they stall before they leave the warehouse because no shipping label is produced. Warehouse staff notice quickly, so incidents here tend to get attention from the floor before the alerts have finished firing.

Use this runbook when:

- carrier-gateway alerts fire for elevated error rates or failing health checks.
- Warehouse or support staff report that labels are not being produced.
- SwiftShip announces an outage or degradation on their status page.

## Key settings

| Setting | Value |
|---|---|
| Maximum retries per carrier request | 5 |
| Escalation | Logistics on-call |

carrier-gateway retries a failed carrier request up to a **maximum of 5 retries per carrier request** before marking it as failed and surfacing it for manual follow up. Retries back off between attempts. Requests that fail with a definitive rejection from SwiftShip (for example an invalid address) are not retried, since sending the same data again will not change the answer.

## First five minutes

1. **Acknowledge the page** so others know someone is on it.
2. **Check the carrier-gateway dashboard.** Look at request volume, error rate by error type, and retry counts. A rising retry count with a flat or falling success rate is the classic sign of a SwiftShip side problem.
3. **Check SwiftShip status.** If SwiftShip has posted an incident, note it in the incident channel and skip to "SwiftShip is degraded" below.
4. **Check recent deploys.** If carrier-gateway was deployed recently and errors began afterwards, treat the deploy as the prime suspect.
5. **Post a short status update** in the incident channel, even if it is just "investigating, more soon".

## Diagnosis

### Errors are mostly authentication failures

SwiftShip credentials may have expired or been rotated without carrier-gateway picking up the new value. Confirm in the logs that the failures are authentication rejections, then check that the credential carrier-gateway is using matches the current one in the secret store. Credential handling follows POL-SEC-01. Do not paste credentials into chat or tickets while investigating.

### Errors are mostly timeouts or server errors from SwiftShip

This is usually a SwiftShip side problem. Confirm with their status page or support channel. carrier-gateway will keep retrying up to its limit, which is the intended behaviour, but watch the retry volume: if many requests are retrying at once, the extra traffic can make a struggling carrier worse.

### Errors are mostly validation rejections

These indicate bad shipment data, typically addresses or package dimensions. They are rarely an outage; more often a single upstream change has started sending data in an unexpected shape. Pull a few failing examples from the logs, identify the common field, and contact the owners of the upstream service.

### carrier-gateway itself is failing health checks

Check resource usage and recent restarts. If the service is crash looping after a deploy, roll back to the previous version. If it is crash looping with no recent change, capture logs and escalate.

## Mitigations

**Roll back a bad deploy.** If a deploy is the likely cause, roll back first and investigate afterwards. A rollback is cheap; a prolonged label outage is not.

**SwiftShip is degraded.** There is little carrier-gateway can do to fix the carrier. Focus on communication: let warehouse leads and support know that labels are delayed, and keep updating the incident channel. Requests that exhaust their retries will need to be resubmitted once SwiftShip recovers; keep a list of affected requests from the failure logs.

**Resubmitting failed requests.** Once the cause is resolved, resubmit failed requests in batches rather than all at once, watching the error rate between batches. Do not resubmit requests that failed on validation without first fixing the data.

## Escalation

**Escalate to the Logistics on-call** when any of the following is true:

- The cause is not identified within a reasonable time and labels are still not being produced.
- A rollback did not help.
- SwiftShip is confirmed degraded and the business needs a decision on how to handle delayed shipments.
- Data looks wrong in a way that may need manual correction.

When escalating, include: when the problem started, what the dashboard shows, what has been ruled out, and what has been tried. A clear handover saves more time than any individual fix.

## After the incident

- Make sure all failed requests have either been resubmitted successfully or handed to the warehouse for manual handling.
- Write a short incident summary in the incident channel.
- If customer impact was significant, open a postmortem.
- If anything in this runbook was wrong or missing, update it.
