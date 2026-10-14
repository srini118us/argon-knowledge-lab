Document ID: POL-RET-03
Version: v1
Title: Data retention
Date: 2025-02-10
Status: Current

# POL-RET-03 Data retention policy

## 1. Purpose

Northwind Logistics keeps data for two reasons: because the business needs it, and because the law or our contracts require it. Keeping data beyond that creates cost and risk with no matching benefit. Every extra year of stored customer data is another year in which it can be breached, mishandled or requested in a dispute.

This policy sets the minimum and maximum periods for which the main categories of data in the Orion order management platform are kept, and explains how deletion is expected to work.

## 2. Scope

This policy applies to:

- All data stored or processed by services that make up the Orion order management platform.
- Copies of that data in backups, exports, analytics stores and logs.
- Data held on our behalf by vendors, to the extent our contracts allow us to direct retention.

It does not cover event streaming retention on the Orion event bus, which is an operational setting governed by POL-DR-02 and the relevant architecture decision records. Events on the bus are transient copies; the records they describe are covered here at their system of record.

## 3. Retention periods

| Data category | Retention period | Starts from |
|---|---|---|
| Order records | 7 years | Order creation |
| Customer PII | 3 years after account closure | Account closure |
| Application logs | 90 days | Log entry written |

### 3.1 Order records

Order records are retained for **7 years**. This includes the order itself, its lines, prices charged, status history, cancellations and associated returns and refunds. The period reflects financial record keeping and audit requirements and the need to resolve late disputes.

Where an order record references customer personal data, the order record is kept for the full period, but personal fields within it are subject to section 3.2 once that period runs out. In practice this means order records are pseudonymised rather than deleted when the customer's PII retention ends: the commercial facts of the order stay, the link to an identifiable person does not.

### 3.2 Customer PII

Customer personally identifiable information is retained for **3 years after account closure**. While an account is open, PII is kept for as long as needed to serve the customer. The clock starts only when the account is closed.

PII here means anything that identifies or could reasonably identify a person: names, email addresses, phone numbers, postal addresses, account identifiers linked to a person, and free text fields where people tend to type personal details (delivery instructions are a common example).

Personal data replicated into other systems, including the CRM, must follow the same period. Service owners that sync customer data to vendors are responsible for making sure deletion propagates.

### 3.3 Application logs

Application logs are retained for **90 days**. Logs are for troubleshooting and incident investigation, not long term storage. If you find yourself wanting logs older than that, it usually means something should be captured as a proper record or metric instead.

Logs must not contain PII where avoidable. If PII does end up in logs, the 90 day period still applies; it does not extend the life of that data.

## 4. Responsibilities

- **Service owners** make sure their service enforces these periods for the data it is system of record for, including automated deletion or pseudonymisation jobs.
- **The Data team** makes sure analytics copies honour the same periods as their sources.
- **The Platform team** provides shared tooling for log retention and for scheduled deletion jobs.
- **Vendor managers** make sure vendor contracts allow us to direct deletion and that vendors confirm it.
- **The privacy lead** reviews compliance with this policy and handles exceptions.

## 5. Deletion

Deletion should be automatic wherever possible. A retention period that depends on someone remembering to run a script is a retention period that will be missed.

Expectations:

1. Each service that stores data in scope has a scheduled job that removes or pseudonymises data past its retention period.
2. Jobs log what they did (counts and categories, never the deleted data itself) so we can show the policy is working.
3. Backups age out on their own schedule. We do not attempt to edit individual records inside backups; instead, restores must re-apply deletions before data is used again.
4. Deletion failures alert the owning team like any other job failure.

## 6. Legal holds

A legal hold overrides this policy for the specific data it covers. When a hold is in place, affected data must not be deleted even if its retention period has ended. Holds are issued by legal counsel, who tells the affected service owners what is covered and when the hold is lifted. Once lifted, normal retention resumes and any overdue deletion is carried out promptly.

## 7. Exceptions

Exceptions to these periods need written approval from the privacy lead, with a clear reason and an end date. Exceptions are reviewed when they expire and are not renewed automatically. "We might need it someday" is not a reason.

## 8. Questions people ask

**Does the 7 year period mean we keep customer names on orders for 7 years?**
No. The order record lives for 7 years, but the customer's personal data on it follows the PII rule. After that runs out, the order is pseudonymised.

**What if a customer asks us to delete their data before 3 years?**
Customer requests are handled through the privacy request process. Some data may need to be kept to meet legal obligations, but anything not required is removed. Talk to the privacy lead.

**Can I keep logs longer for a hard to reproduce bug?**
Extract what you need into the ticket, without personal data, and let the logs expire. If a pattern needs long term visibility, turn it into a metric.

## 9. Review

This policy is reviewed periodically by the privacy lead with input from service owners, and whenever a legal or contractual change affects retention.
