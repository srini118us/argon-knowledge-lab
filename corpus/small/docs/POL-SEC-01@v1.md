| | |
|---|---|
| **Document ID** | POL-SEC-01 |
| **Version** | v1 |
| **Title** | Platform security policy |
| **Date** | 2024-01-22 |
| **Status** | Superseded |
| **Superseded by** | POL-SEC-01 v2 |

> This version is superseded by POL-SEC-01 v2. It is retained for audit history. Teams should follow v2.

# Platform security policy

## 1. Purpose

This policy sets the minimum security controls for every service that runs as part of the Orion order management platform at Northwind Logistics. It exists so that individual teams do not have to make their own decisions about the basics, and so that anyone reviewing a service can check it against a single, stable list of expectations.

The policy is intentionally short. It does not try to cover application security in general, secure coding practices or access to production for humans. Those are covered by separate standards. This document is about how services talk to each other and how they handle secrets.

## 2. Scope

This policy applies to:

- every service in the Orion platform, whatever team owns it
- every environment that holds production data
- any new service before it is allowed to receive production traffic

Non production environments that hold only synthetic data are encouraged to follow the same controls, because configuration that differs between environments tends to fail at the worst moment, but they are not formally in scope.

## 3. Policy statements

### 3.1 Service to service transport

**mTLS is required between services.** Every call from one Orion service to another must use mutual TLS, so that both sides present and verify a certificate before any application data is exchanged.

The reasoning is straightforward. Orion services handle orders, payments and customer details. Relying on network placement alone to decide who may call whom has not held up well in the industry, and it makes it too easy for a misconfigured or compromised workload to reach services it should not. With mTLS, each service has a verifiable identity at the transport layer and traffic is encrypted in transit as a matter of course.

Plain text calls between services are not permitted, including calls that never leave a single host or cluster. Exceptions require written approval from the security function and must be time limited.

### 3.2 Secrets storage

**Secrets are stored in HashiCorp Vault.** This covers, at minimum:

- database credentials
- API keys and credentials for external vendors
- signing and encryption keys
- service certificates and their private keys

Secrets must not be placed in source code, container images, plain configuration files, CI variables visible to people, tickets or chat. Services read secrets from Vault at runtime using their own identity, and are granted access only to the secrets they need.

If a secret is found outside Vault, treat it as exposed: rotate it and then move the new value into Vault.

### 3.3 Rotation

**Secrets and keys are rotated every 180 days.** Every secret and key covered by 3.2 must be replaced at least once in each 180 day period. Teams may rotate more often; nothing in this policy discourages that.

Rotation must be possible without downtime. In practice that means a service must be able to pick up a new secret without a redeploy, or must support a period in which both the old and new value are valid. A service that can only rotate by being taken offline is not compliant, even if it does rotate on time.

Rotation is also required immediately, regardless of schedule, when:

- a secret is suspected of being exposed
- a person with access to a secret leaves the team that uses it, where the secret could have been copied
- a vendor notifies us of a compromise on their side

## 4. Responsibilities

| Role | Responsibility |
|---|---|
| Service owning team | Implements the controls for its services, keeps rotation on schedule, and fixes findings |
| Platform team | Operates the shared tooling that makes mTLS and Vault usable by every team |
| Security function | Owns this policy, grants exceptions and reviews compliance |

## 5. Compliance and review

Services are checked against this policy when they are first onboarded to production and periodically after that. Findings are raised with the owning team and tracked to closure. A service with an open, unapproved exception may be blocked from releasing until the finding is resolved.

The security function reviews this policy periodically, and sooner if an incident or a change in the platform shows it is out of date.

## 6. Exceptions

Exceptions must be requested in writing, explain why the control cannot be met, describe compensating controls and include an end date. Open ended exceptions are not granted.

## 7. Related documents

- POL-SEC-01 v2 (supersedes this version)
- Service onboarding checklist
- Vault usage guide maintained by the Platform team
