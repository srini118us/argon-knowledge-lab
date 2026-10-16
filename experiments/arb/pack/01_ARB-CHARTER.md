# ARB-CHARTER@v1: Architecture Review Board charter

| Field | Value |
|---|---|
| Document | ARB-CHARTER |
| Version | v1 |
| Status | Current |
| Effective | 2026-02-01 |
| Owner | Office of the Chief Architect |

## 1. Purpose

The Architecture Review Board (ARB) reviews every proposal that sends Northwind Logistics data to an external vendor or changes how data leaves the internal network. The ARB exists so that delivery teams get one consistent answer, grounded in written policy, instead of negotiating rule by rule with security, legal and operations.

## 2. Sources of authority

The ARB decides only from the documents in its review pack: the security policy, the data classification standard, regional annexes, the data residency standard, the network standard, architecture decision records, vendor contracts, the exception register and the change calendar. Board members do not apply unwritten preferences.

**CH-2.1** Where two versions of a document exist, only the version whose status is Current applies. A superseded version may be cited as history but never as authority.

**CH-2.2** Where a regional annex sets a stricter requirement than the global security policy for the same data, the annex applies to that data and replaces the global requirement for it. Data about subjects outside that region remains under the global requirement.

**CH-2.3** A waiver in the exception register applies only if all of the following hold: it names the rule being waived; it names the vendor in the proposal; the proposal's planned go live date falls within the waiver's validity period, both dates inclusive; and every scope limit written in the waiver is met. A waiver never covers a rule it does not name. A waiver's compensating controls become part of the resulting condition; the proposal does not need to describe them.

**CH-2.4** Waiver validity and freeze windows are judged against the proposal's planned go live date, not the date of the review.

## 3. Decision procedure

The ARB evaluates every rule in the pack against the proposal, then decides:

**CH-3.1** A rule that the proposal fails, and that no applicable waiver covers, is a violation.

**CH-3.2** A rule that the proposal fails but an applicable waiver covers is a condition: the proposal may proceed only while the waiver remains valid and its compensating controls are in place.

**CH-3.3** A go live date inside a change freeze window is a condition under the change calendar.

**CH-3.4** The decision is:
* **reject** if there is at least one violation. When rejecting, the ARB lists every violation and lists no conditions.
* **approve_with_conditions** if there are no violations and at least one condition. The ARB lists every condition.
* **approve** if there are no violations and no conditions.

## 4. Citations

**CH-4.1** Every violation and condition is cited by document, version and clause, in the form `DOC_ID@VERSION#CLAUSE`, for example `SEC-POL@v3#SP-4.2`. A waiver relied on is cited the same way, for example `EXC-REG@2026-10#W-07`. Where a vendor's contract determines a finding (for example its data processing agreement or hosting region), the contract is cited by `DOC_ID@VERSION`.

## 5. Meeting cadence

The ARB meets every Tuesday. Proposals must be submitted by the preceding Thursday with a completed integration questionnaire. Emergency reviews may be requested by the on call architect but follow the same decision procedure.

## Revision history

| Version | Date | Change |
|---|---|---|
| v1 | 2026-02-01 | First issue, replacing informal security sign off |
