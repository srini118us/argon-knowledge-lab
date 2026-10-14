```
Document ID:   RB-CARRIER-01
Version:       v2
Title:         carrier-gateway incidents
Date:          2025-08-20
Status:        Current
Supersedes:    RB-CARRIER-01 v1
```

# Runbook: carrier-gateway incidents

## What changed in v2

If you used v1 of this runbook, read this first.

- **Maximum retries per carrier request is now 3.** This was reduced from the v1 limit after PM-2025-014, where retries from carrier-gateway piled up into a retry storm against SwiftShip.
- **Retries now use exponential backoff with a 2 second base.** Each retry waits roughly twice as long as the one before, starting from 2 seconds.
- The escalation section now spells out when to contact SwiftShip support and reminds you to check the contracted support hours first.

Everything else is broadly the same as v1, with some tidying.

## Scope

This runbook covers incidents where carrier-gateway is failing, degraded or slow in its communication with SwiftShip, the carrier API we use for shipment booking, labels and tracking. Typical symptoms:

- Label generation failures reported by warehouse staff or downstream services
- Error rate alerts on carrier-gateway
- Elevated latency on calls to SwiftShip
- Rate limit errors returned by SwiftShip
- A growing backlog of carrier requests waiting to be processed

It does **not** cover problems inside shipping-service that never reach carrier-gateway, or issues with notifications to customers. If you find the problem is upstream of carrier-gateway, hand it over and close your part of the incident.

## Before you start

- Open an incident channel and post that you are investigating. Even a one line "looking at carrier-gateway errors" stops three people from debugging the same thing in parallel.
- Have the carrier-gateway dashboard and logs open.
- Have CT-SWIFT-2024 (and any amendments) to hand in case you need vendor support.

## Retry policy reference

Every outbound carrier request from carrier-gateway follows this policy:

| Setting | Value |
|---|---|
| Maximum retries per carrier request | 3 |
| Backoff | Exponential, 2 second base |

Why it matters: during PM-2025-014 the previous, more generous retry limit meant that every failing request multiplied into several more requests just as SwiftShip was struggling. That pushed us over the SwiftShip rate limit and turned a partial problem into a full outage. The lower cap and the backoff are there so that carrier-gateway backs off when SwiftShip is in trouble instead of piling on.

**Do not raise the retry limit or shorten the backoff during an incident** to "push things through". That is the exact pattern that caused PM-2025-014. If you think the policy is wrong, raise it after the incident.

## Triage

### Step 1: Is it us or them?

Look at the shape of the errors.

- **Rate limit errors from SwiftShip** usually mean we are sending too much. Go to Step 2.
- **Server errors or timeouts from SwiftShip across all request types** usually mean SwiftShip is degraded. Go to Step 3.
- **Client errors (bad request, validation failures) on a subset of requests** usually mean a data problem or a change on one side. Go to Step 4.
- **Errors before any request leaves carrier-gateway** (startup failures, crashes, configuration errors, credential failures) mean the problem is ours. Go to Step 5.

Check the deploy history for carrier-gateway. If a deploy went out shortly before errors started, roll it back first and investigate second.

### Step 2: Rate limit errors

1. Confirm request volume on the dashboard. Is there a spike in incoming carrier work, or is the volume normal but retries are inflating it?
2. Check that the retry policy in the running configuration matches the table above. A misconfigured instance with an old retry setting can cause trouble on its own.
3. If incoming volume is genuinely high (a promotion, a backlog being released), consider pausing non urgent work such as bulk tracking refreshes so label generation keeps priority.
4. Scaling carrier-gateway up does **not** help with rate limits. More instances share the same SwiftShip allowance and simply hit the limit faster.

### Step 3: SwiftShip degraded

1. Check SwiftShip's status page and any recent notices forwarded by vendor management.
2. Let the retry policy do its job. Requests that exhaust their retries will fail and need to be reprocessed once SwiftShip recovers.
3. Post in the incident channel that label generation is delayed, so warehouse and customer facing teams can set expectations.
4. If the degradation persists, contact SwiftShip support (see Escalation).

### Step 4: Client errors on a subset of requests

1. Pull sample failing requests from the logs and compare them to successful ones. Common culprits are address formats, missing fields and unexpected characters.
2. Check whether SwiftShip announced an API change. Vendor change notices are forwarded to the engineers who maintain carrier-gateway, but they are easy to miss.
3. If the bad data originates upstream, hand over to the owners of the upstream service with the sample payloads.

### Step 5: carrier-gateway itself is unhealthy

1. Check instance health, restarts and resource usage.
2. Check that SwiftShip credentials are present and valid. An expired or rotated credential looks like a sudden wall of authentication failures.
3. Roll back the most recent deploy or configuration change if there is one.
4. Restart unhealthy instances only after you have captured logs; restarts destroy evidence.

## Recovery

Once SwiftShip is responding normally:

1. Watch the error rate return to baseline before declaring recovery.
2. Identify carrier requests that failed after exhausting their retries during the incident. These need to be reprocessed.
3. Reprocess them gradually. Releasing the whole backlog at once can trip the SwiftShip rate limit again. If in doubt, go slower.
4. Confirm with the warehouse that labels are printing.

## Escalation

- **Escalate to the Logistics on-call** if any of the following is true: you cannot identify the cause within a reasonable time, label generation is fully down, the backlog is growing and not draining, or you need a decision about pausing work.
- **Contact SwiftShip support** when the evidence points to a problem on SwiftShip's side. Do this **within the contracted support hours** set out in CT-SWIFT-2024 and its amendments. Check the current terms before relying on a response; do not assume from memory.

When you open a SwiftShip ticket, include:

- The affected operations
- Start time in UTC and Eastern Time
- Sample request identifiers from carrier-gateway logs
- The exact error responses
- Any recent changes on our side

If you are outside the contracted support hours, open the ticket anyway so it is waiting for the vendor, and focus on containment: keep retries within policy, keep the backlog safe, and keep downstream teams informed.

## After the incident

- Write up a postmortem for anything that affected label generation for customers or warehouses.
- If a step in this runbook was wrong, missing or confusing, fix it. A runbook only stays useful if the people who use it update it.

## Related documents

- PM-2025-014: Carrier label outage
- CT-SWIFT-2024: SwiftShip carrier services agreement
- RB-CARRIER-01 v1 (superseded)
