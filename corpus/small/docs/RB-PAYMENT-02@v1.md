# RB-PAYMENT-02: Payment failures

- **Document ID:** RB-PAYMENT-02
- **Version:** v1
- **Title:** Payment failures
- **Date:** 2025-02-03
- **Status:** Current

---

## When to use this runbook

Use this runbook when alerts or reports indicate that payments on the Orion platform are failing. Typical signals:

- An alert on elevated payment failure rate from payment-service.
- Customer support reporting that customers cannot complete checkout.
- A visible build up of items on the payment-retry queue.
- Error logs in payment-service showing failed responses from PayNimbus.

If the problem is clearly a single customer's card being declined, this runbook is not the right place. That is a normal business outcome, not an incident.

## Background: how failed payments are handled

Northwind Logistics uses **PayNimbus** as its payment gateway. payment-service is the only Orion service that talks to PayNimbus.

When a payment attempt to PayNimbus fails for a reason that might succeed later (for example a gateway error or a timeout, as opposed to a hard decline), **the failed payment is placed on the payment-retry queue**. **payment-service processes the payment-retry queue hourly.** On each run it picks up the queued payments and attempts them again against PayNimbus.

Two consequences matter during an incident:

1. A short PayNimbus blip often resolves itself. Payments that failed during the blip will be retried on the next hourly run without anyone doing anything.
2. During a longer outage the payment-retry queue will keep growing until PayNimbus recovers. That is expected behaviour, not a second problem.

### There is no failover

**PayNimbus has no secondary provider. There is no automatic failover.** If PayNimbus is down, payments cannot be taken through another gateway, and no switch exists for the on-call engineer to flip. Do not spend incident time looking for one. The job during a PayNimbus outage is to confirm it, communicate it, keep the retry path healthy and make sure queued payments are processed once the gateway is back.

## Triage

Work through these in order. Write what you find in the incident channel as you go.

### Step 1: Is it us or PayNimbus?

- Check payment-service health and recent deployments. A bad deploy is the most common cause of a sudden spike in failures that coincides with a release.
- Look at the error responses payment-service is receiving. Are they errors returned by PayNimbus, or are requests failing before they ever leave payment-service (configuration, credentials, networking)?
- Check the PayNimbus status page and any vendor notifications.

If failures started right after a payment-service deploy, roll back first and investigate afterwards.

### Step 2: Is the failure hard or soft?

- **Hard failures** (declines, invalid card details, fraud rejections) should not be retried and should not end up on the payment-retry queue. A sudden increase in these is usually a business or fraud question rather than a platform incident. Hand it to the relevant business contact.
- **Soft failures** (gateway errors, timeouts) are the ones placed on the payment-retry queue.

If hard failures are ending up on the retry queue, that is a bug in payment-service. Raise it as part of the incident.

### Step 3: Is the retry path healthy?

- Confirm the hourly retry job ran at its last scheduled time. Check payment-service logs for the start and end of the most recent run.
- Confirm the job is actually reducing the queue when PayNimbus is healthy. If the queue grows while PayNimbus is fine and the job is running, something is wrong with the retry logic itself.
- If the job did not run, check whether payment-service was healthy and deployed at that time.

## Mitigation

### Scenario A: PayNimbus outage

1. Declare an incident and set severity according to customer impact.
2. Post a status update for customer support so they can set expectations with customers.
3. Open a support case with PayNimbus and record the reference in the incident channel.
4. Leave the payment-retry queue alone. Do not purge it. It holds the payments that will be retried once the gateway recovers.
5. Monitor for recovery. Once PayNimbus is back, either wait for the next hourly run or, if business impact justifies it, trigger a manual run of the retry job using the standard operational tooling.
6. Confirm the queue drains and the failure rate returns to normal before closing.

### Scenario B: payment-service fault

1. Roll back the most recent payment-service deployment if one coincides with the start of failures.
2. If no deploy is involved, check credentials and configuration for the PayNimbus connection.
3. Once fixed, let the retry job process the queued payments, or trigger it manually.

### Scenario C: retry job not running

1. Check whether the scheduler for the job is healthy.
2. Trigger a manual run once the cause is fixed.
3. Watch the following run to confirm the schedule is back to hourly.

## Things not to do

- Do not purge or delete items on the payment-retry queue to "clear the alert". Those are real customer payments.
- Do not retry hard declines manually.
- Do not change PayNimbus credentials during an incident unless you have confirmed they are the cause.
- Do not promise customers or support a specific recovery time for a PayNimbus outage. We do not control it.

## Escalation

Escalate according to the payment-service on-call rotation shown in the paging tool. For a confirmed vendor outage, also inform the incident commander so customer communication can be coordinated.

## After the incident

- Record the start and end of the failure window and the number of payments that went through the retry path.
- Confirm all queued payments were either completed or explicitly resolved.
- File follow ups for any gaps found in alerting or in this runbook.
