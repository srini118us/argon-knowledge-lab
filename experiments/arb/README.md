# Experiment 2: Architecture Review Board decisions (design, not yet run)

**Question:** when all the evidence is in context, does Gemini 4 Argon make better multistep architecture decisions than Gemini 3.8 Flash, and does high thinking change the answer?

Status: built and validated offline on 2026-10-16. **No API calls have been made.** Experiment 1 (repository root) is unchanged.

## Why this design

In Experiment 1 most RAG errors coincided with missing retrieved evidence, and long context reached 50 of 50 for both models. This experiment removes retrieval entirely: every model receives the full policy pack (about 4.4K tokens) with every case. What remains is reasoning: classifying data, applying rules that interact, resolving conflicts between policies, and checking waiver validity and scope.

## Scenario

Northwind Logistics' Architecture Review Board decides proposals that send data to external vendors. The pack (`pack/`) holds 16 documents:

| Document | Role in the reasoning |
|---|---|
| ARB-CHARTER@v1 | Decision procedure, precedence (stricter regional annex wins), waiver applicability, citation format |
| DCS-01@v2 | Data classification: C1 internal, C2 personal, C3 card data |
| SEC-POL@v3 (current) and SEC-POL@v2 (superseded) | Vendor eligibility, transport, retention, encryption; v2 is looser on two rules (distractor) |
| AX-EU@v1 | EU annex: 14 day retention for EU data subjects, not waivable by global waivers |
| DRS-01@v1 | Residency: EU personal data only with EU hosted vendors |
| NET-STD@v2 | Zone Z3 egress must pass the egress proxy |
| ADR-028, ADR-031, ADR-033 | Gateway rule (ADR-031 D1) plus two irrelevant ADRs |
| 4 vendor contracts | Hosting region and DPA coverage per vendor |
| EXC-REG@2026-10 | Waivers: one limited to US data subjects that ends 2026-12-31, one with a 60 day limit, one with a compensating control, one retired |
| CHG-CAL@2026 | Peak freeze 2026-12-14 to 2027-01-04, inclusive; go live inside it is a condition |

Each case is a short prose proposal, for example:

> The team proposes to send delivery addresses to Parcelytics. The data concerns customers and drivers in the US and the EU. ... Data is transferred over standard HTTPS (server side TLS). Parcelytics will retain the data for 20 days. ... Planned production go live: 2026-11-05.

The model returns `decision` (approve, approve_with_conditions, reject), `violations` and `conditions` (rule IDs), `citations` (`DOC_ID@VERSION#CLAUSE`) and a short rationale.

## The 12 test cases

| Case | Expected | What it requires |
|---|---|---|
| T01 | approve | Do not over apply: US data, day after the freeze ends, US vendor is fine for US data |
| T02 | approve_with_conditions (SP-3.1, CF-1) | Classify C2, see TLS fails v3, find the active US only waiver, notice the freeze |
| T03 | reject (SP-3.1, DR-1, AX-EU-1) | Waiver out of scope (EU subjects), residency, and the EU annex retention limit |
| T04 | approve_with_conditions (SP-4.1) | Retention fails, waiver W-12 still valid on that go live date |
| T05 | approve_with_conditions (SP-4.2) | Encryption fails, waiver W-15 covers it with a compensating control |
| T06 | reject (SP-2.1, NZ-2) | Mixed data takes the highest class; vendor DPA covers C1 only; Z3 without proxy |
| T07 | approve | Telemetry is C1, so transport, retention, encryption and residency do not apply |
| T08 | reject (SP-2.1, SP-2.2, D1) | Card data never leaves; DPA excludes C3; direct API call bypasses the gateway |
| T09 | reject (AX-EU-1) | Waiver covers the global retention rule for US data but cannot waive the EU annex |
| T10 | approve_with_conditions (SP-4.2, CF-1) | Waiver applies; go live on the last, inclusive freeze day |
| T11 | reject (SP-3.1) | Waiver expired 2026-12-31; go live 2027-01-15; v2 would wrongly allow TLS |
| T12 | reject (DR-1) | Encryption waiver applies, but EU residency cannot be waived |

Test split: 2 approve, 4 approve_with_conditions, 6 reject. Three dev cases are used only for the pilot.

## Ground truth and why it is defensible

* **Computed, not judged.** `engine.py` applies the rules in `spec/policy.json` to structured proposals; `check_cases.py --write` freezes the result in `spec/key.json`. Models see only the prose pack and the prose proposal.
* **Pack and spec agree.** Offline checks confirm that every rule, waiver, date, retention limit and contract the engine uses is stated in the pack under the right document.
* **No lookups.** Each case is tested against 20 mutations that model plausible mistakes (skip classification, forget the annex, ignore waiver dates or scope, use the superseded policy, misread the freeze end, over apply residency, and so on). A reject or conditions case is accepted only if at least 3 skipped steps change its outcome; an approve case only if at least 2 over applied rules do. All 12 pass: reject and conditions cases need 3 to 7 steps each; approve cases carry 2 or 3 traps.
* **Every fact is in the proposal.** A check confirms that each rendered proposal states every structured attribute.
* **Blind review.** An independent reviewer (a separate Claude agent given only the pack and the 15 proposals, never the key or engine) decided every case. It matched the key on all 15. It also listed wording a careful reader could interpret differently; these were fixed before freezing: a waiver purpose phrase that read like a scope limit, unclear handling of compensating controls (now stated as part of the condition, CH-2.3), the evaluation date (now the go live date, CH-2.4, with no case dated in the past), and proposal wording that implied every proposal involved personal data.
* **Remaining judgment calls, stated in the pack:** C3 data violates both SP-2.1 (the DPA excludes C3) and SP-2.2 (T08); on reject, conditions are not listed (CH-3.4), so waivers that would apply are not counted (T09, T12).

## Scoring (`score_arb.py`)

| Metric | Definition |
|---|---|
| Decision accuracy | Exact match of the three way decision |
| Fully correct | Decision, violation set and condition set all exact (primary metric) |
| Evidence valid | Fully correct and every required clause, waiver and contract cited |
| Violation and condition F1 | Set precision and recall over rule IDs |
| Superseded reliance | Cites SEC-POL@v2 for a clause without citing v3 for the same clause |
| Unknown citations | Cites a document or clause that does not exist in the pack |
| Cost, latency, tokens | From API usage fields, plus cost per fully correct case |

Rule IDs are parsed tolerantly (`SEC-POL@v3#SP-3.1` and `SP-3.1` both count). Waiver IDs listed as conditions are ignored rather than penalized.

## Model configurations

Identical system prompt, pack, proposal text and JSON schema for every arm; pack first and proposal last; `max_output_tokens` 16,000; no tools; no retries.

| Arm | Model | Thinking |
|---|---|---|
| 1 | gemini-3.8-flash | medium |
| 2 | gemini-3.8-flash | high |
| 3 | gemini-4-argon | medium |
| 4 | gemini-4-argon | high |

## Cost estimate and spending guard

Preflight from `run_arb.py --dry-run` (introductory prices; output plus thinking assumed at 3,000 tokens per case for medium and 8,000 for high, to be replaced by pilot measurements):

| Run | Calls | Expected | Worst case |
|---|---|---|---|
| Pilot, 3 dev cases | 12 | about $0.53 | $1.40 |
| Test, 12 cases | 48 | about $2.12 | $5.59 |
| **Total** | 60 | **about $2.65** | capped at $5.00 |

Guard: before every call, the ledger total plus that call's worst case (input estimate plus 16,000 output tokens at the output rate) must stay within `--cap`, or the run stops. The ledger (`results/ledger.jsonl`) persists across runs, so the $5 cap covers pilot and test together. A failed call is charged at its worst case. If any call costs more than its worst case, the run stops and reports that the output cap was not honoured. Every call records its interaction ID and UTC timestamp for billing reconciliation.

## Plan

1. **Pilot** on 3 dev cases (about $0.53). Check that `max_output_tokens` is accepted, outputs parse, and measured token counts. If Flash at medium gets all 3 dev cases fully correct, harden the dev cases only, never the test cases.
2. **Freeze commit** of pack, cases, key and runner.
3. **Test run**, 12 cases x 4 arms (about $2.12).
4. **Repeated trials (separate approval):** 12 cases cannot establish a difference. If any two arms differ by 3 or more fully correct cases, run 2 more trials (about $4.25 more). Otherwise report the tie.

## Limitations known in advance

* One synthetic policy pack written by the experimenter; the rules are deliberately crisp, so real policy ambiguity is not tested.
* 12 test cases, one trial: descriptive only.
* The pack is short (about 4.4K tokens), so this tests reasoning, not long context.

## Commands

```powershell
.\.venv\Scripts\python.exe experiments\arb\check_cases.py                       # free: validate cases and key
.\.venv\Scripts\python.exe -m pytest -q                                         # free: all offline tests
.\.venv\Scripts\python.exe experiments\arb\run_arb.py --split dev --cap 5 --dry-run   # free: preflight
```
