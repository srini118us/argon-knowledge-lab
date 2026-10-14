| Document ID | POL-SEC-01 |
|---|---|
| Version | v2 |
| Title | Platform security policy |
| Date | 2025-03-03 |
| Status | Current |
| Supersedes | POL-SEC-01 v1 |

# Platform security policy

## 1. Purpose

This policy sets the minimum security requirements for every service that runs as part of the Orion order management platform at Northwind Logistics. It exists so that individual teams do not have to work out the baseline for themselves, and so that reviewers have a single reference when checking a design or a change.

Where a requirement here conflicts with a team level guideline, this policy wins. Teams may go further than this policy, but not less far.

## 2. Scope

This policy applies to:

- All Orion services, whether customer facing or internal only.
- Supporting jobs, scripts and tooling that access Orion data or credentials.
- Integrations with external vendors, on the Orion side of the connection.

It does not cover corporate IT systems, which are governed separately.

## 3. What changed in v2

- **Secret and key rotation interval reduced.** Secrets and keys are now rotated every 90 days. In v1 the interval was 180 days.
- The transport security section now cross references the architecture decision on application level service authentication, to make clear that the two requirements apply together.
- Wording throughout has been tightened. The intent of the remaining requirements is unchanged from v1.

## 4. Transport security between services

**mTLS is required between services.** Every network connection from one Orion service to another must use mutual TLS, so that both the client and the server present and verify certificates.

Rationale: plain TLS protects the connection from eavesdropping and lets the client verify the server, but it says nothing about who the client is. Requiring both sides to authenticate at the transport layer means that a process which has merely found its way onto the internal network cannot open connections to Orion services. It also provides a layer of protection that is independent of application code, so a bug in one service's authorization logic does not by itself expose it to arbitrary callers.

Requirements:

- Connections that do not complete mutual authentication must be refused, not downgraded.
- Certificates are issued by the platform's internal certificate authority. Services must not use self signed certificates in any shared environment.
- Certificates are treated as keys for the purposes of rotation (see section 6).

Application level caller identity and authorization are separate concerns and are covered by the relevant architecture decisions, for example ADR-011 for service to service authentication. Transport security and application authorization are both required; one does not replace the other.

## 5. Secrets management

**Secrets are stored in HashiCorp Vault.** This includes, without exception:

- Database credentials.
- API keys and credentials for external vendors.
- OAuth2 client secrets for service identities.
- Private keys and certificates.
- Signing and encryption keys.

Requirements:

- Secrets must not be committed to source control, in any branch, including in test fixtures or example configuration.
- Secrets must not be baked into container images or build artifacts.
- Services read secrets from HashiCorp Vault at runtime, using their own service identity, and are granted access only to the secrets they need.
- Secrets must not be written to logs, metrics, traces or error messages. Logging libraries should redact known secret fields by default.
- Human access to production secrets is by exception, must be justified, and is audited.

If a secret is found anywhere other than HashiCorp Vault, treat it as compromised: rotate it immediately and then remove the copy.

## 6. Rotation

**Secrets and keys are rotated every 90 days.** This interval was **reduced from 180 days** in this version of the policy.

Why the change: a shorter interval limits how long a leaked credential remains useful to an attacker, and frequent rotation forces teams to keep their rotation procedures working. Under the previous interval, rotation happened rarely enough that procedures were often forgotten or broken by the time they were needed, and some rotations turned into small incidents of their own.

Requirements:

- Every secret and key has a recorded owner and a recorded last rotation date.
- Rotation should be automated wherever the underlying system supports it. Manual rotation is acceptable only where automation is not possible, and must follow a written procedure.
- Services must be able to pick up rotated secrets without a full redeploy, or the rotation procedure must include the redeploy explicitly.
- Rotation is required immediately, regardless of schedule, when compromise is suspected or when a person with access leaves a role that required it.

Teams moving from the old interval to the new one should prioritise credentials for external vendors and anything that grants write access to customer or payment data.

## 7. Logging and audit

- Security relevant events, such as authentication failures, authorization denials and access to secrets, must be logged with enough context to reconstruct what happened.
- Logs must not contain secrets or full payment details.
- Audit logs must be protected against modification by the services that produce them.

## 8. Exceptions

Exceptions to this policy must be requested in writing, with the reason, the compensating controls in place, and an expiry. Exceptions are reviewed by the security function. An exception without an expiry will not be approved.

## 9. Compliance

Compliance with this policy is checked during design review and periodically across running services. Non compliance found in review must be fixed before launch. Non compliance found in a running service is tracked as a defect with an owner and a target date.

## 10. Related documents

- POL-SEC-01 v1 (superseded by this version).
- ADR-011, Service to service authentication.
