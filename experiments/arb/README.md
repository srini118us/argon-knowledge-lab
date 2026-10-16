# Experiment 2: Architecture Review Board decisions

**Question:** when all the evidence is in context, does Gemini 4 Argon make better multistep architecture decisions than Gemini 3.8 Flash, and does high thinking change the answer?

Status: run once on 2026-10-16 (12 test cases x 4 arms). Experiment 1 (repository root) is unchanged.

## Results (single run, 12 test cases)

Run file: `results/runs/test_20261016_152247.jsonl`. Scored by `score_arb.py`. Costs are usage based estimates.

| Arm | Fully correct | Decision correct | Evidence valid | Est. cost | Cost per fully correct | Median latency | Output plus thinking per case |
|---|---|---|---|---|---|---|---|
| Flash, medium | 12/12 | 12/12 | 12/12 | $0.16 | $0.014 | 18 s | 2,620 |
| Argon, medium | 12/12 | 12/12 | 12/12 | $0.21 | $0.018 | 11 s | 713 |
| Argon, high | 11/12 | 11/12 | 11/12 | $1.27 | $0.115 | 67 s | 9,513 |
| Flash, high | 10/12 | 10/12 | 10/12 | $0.47* | $0.047 | 72 s | 9,563 |

\* Excludes two failed calls that returned no usage; the guard booked them at worst case ($0.25).

Every answer that came back was fully correct: exact decision, exact violation and condition sets, all required citations, no reliance on the superseded policy, no citations to clauses that do not exist. All three misses are answers that never arrived:

| Case | Arm | Cause |
|---|---|---|
| T05 | Flash, high | Server disconnected after 3,247 s; no answer |
| T12 | Flash, high | Server disconnected after 272 s; no answer |
| T12 | Argon, high | Used 31,997 thinking tokens of the 32,000 cap, 3 output tokens; no answer |

### Findings (this run only)

1. **No accuracy difference at medium thinking.** Both models were fully correct on all 12 multistep cases. The decision rule set before the run (repeat only if two arms differ by 3 or more cases) does not call for repeated trials.
2. **Argon at medium was the most token efficient arm:** about 700 output plus thinking tokens per case against Flash's 2,600, with the lowest median latency (11 s against 18 s). Its estimated cost was about 1.3 times Flash's.
3. **High thinking did not help either model here.** It cost 3 to 6 times more than medium, was 4 to 6 times slower, and produced every miss: Argon exhausted a 32K budget on T12 (and a 16K budget on DEV1 in the pilot), and Flash lost two calls to server disconnects.
4. **The test hit a ceiling.** Perfect scores at medium mean these 12 cases, though they require 3 to 7 reasoning steps each, were not hard enough to separate the models on accuracy. This is the main limitation of the result.

### Harness defects found during the run

* **The 10 minute timeout was not enforced.** The T05 call ran 54 minutes before the server dropped it. `HttpOptions.timeout` did not bound a long running Interactions call in this SDK version. A future run needs a hard timeout around each call.
* Earlier pilot attempts used a key from a free tier project (503 and 429 errors, no tokens processed); see Pilot findings.

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

Identical system prompt, pack, proposal text and JSON schema for every arm; pack first and proposal last; `max_output_tokens` 32,000 (includes thinking); no tools; no client retries; 10 minute timeout per call; cases run in case major order so every arm answers the same cases even if the cap stops the run.

| Arm | Model | Thinking |
|---|---|---|
| 1 | gemini-3.8-flash | medium |
| 2 | gemini-3.8-flash | high |
| 3 | gemini-4-argon | medium |
| 4 | gemini-4-argon | high |

## Pilot findings (2026-10-16, dev cases)

* Earlier attempts failed with 503 and 429 errors from a key on a free tier project; no tokens were processed. The guard booked them at worst case ($0.38 in the ledger, not real spend).
* With a billed key, 9 of 12 calls completed and every answer parsed; all 9 decisions matched the key. Measured output plus thinking per case: about 1K to 2K at medium; about 13K for Flash at high.
* Argon at high thinking on DEV1 used 15,997 thinking tokens and 3 output tokens, exactly the 16,000 cap, and returned no answer. The cap is honoured and includes thinking. The guard stopped the run because actual cost beat the worst case by $0.001: the input estimate (characters / 4) was 12% low.
* Changes after the pilot: cap raised to 32,000 for all arms; input estimate margin 1.25; client retries off with a 10 minute timeout; case major order; an `--arms` filter for single arm reruns.

## Cost estimate and spending guard

Preflight after the pilot (introductory prices; output plus thinking assumed at 2,000 tokens per case for medium and 20,000 for high; input estimate with a 1.25 margin):

| Run | Calls | Expected | Worst case |
|---|---|---|---|
| Pilot, 3 dev cases (done) | 10 | $0.39 actual | |
| DEV1 rerun, Argon high only | 1 | about $0.21 | $0.33 |
| Test, 12 cases | 48 | about $4.02 | $10.95 |
| **Test, actual** | 48 | **$2.11 measured** plus $0.25 booked for 2 failed calls | |

**Experiment total in the ledger: $3.27.** Of this, about $2.65 is measured usage (pilot $0.39, DEV1 rerun $0.15, test $2.11) and $0.63 is worst case booking for calls that failed without usage data (free tier errors and two disconnects); their real cost is not known and is most likely lower.

The ledger already holds $0.77 ($0.39 real plus $0.38 booked for failed free tier calls). **With a $5 cap the test run is likely to stop before the last cases**; case major order keeps the arms comparable if it does, but a complete run needs a higher cap (about $7) or fewer arms. That is the owner's decision before the test run.

Guard: before every call, the ledger total plus that call's worst case (input estimate plus 16,000 output tokens at the output rate) must stay within `--cap`, or the run stops. The ledger (`results/ledger.jsonl`) persists across runs, so the $5 cap covers pilot and test together. A failed call is charged at its worst case. If any call costs more than its worst case, the run stops and reports that the output cap was not honoured. Every call records its interaction ID and UTC timestamp for billing reconciliation.

## Plan

1. **Pilot** on 3 dev cases (about $0.53). Check that `max_output_tokens` is accepted, outputs parse, and measured token counts. If Flash at medium gets all 3 dev cases fully correct, harden the dev cases only, never the test cases.
2. **Freeze commit** of pack, cases, key and runner.
3. **Test run**, 12 cases x 4 arms (about $2.12).
4. **Repeated trials (separate approval):** 12 cases cannot establish a difference. If any two arms differ by 3 or more fully correct cases, run 2 more trials (about $4.25 more). Otherwise report the tie.

## Limitations

* One synthetic policy pack written by the experimenter; the rules are deliberately crisp, so real policy ambiguity is not tested.
* 12 test cases, one trial: descriptive only.
* The pack is short (about 4.4K tokens), so this tests reasoning, not long context.
* Ceiling effect: medium arms were perfect, so the experiment cannot rank the models on accuracy.
* High thinking results depend on the 32K output cap; a larger cap might have let Argon finish T12.

## Commands

```powershell
.\.venv\Scripts\python.exe experiments\arb\check_cases.py                       # free: validate cases and key
.\.venv\Scripts\python.exe -m pytest -q                                         # free: all offline tests
.\.venv\Scripts\python.exe experiments\arb\run_arb.py --split dev --cap 5 --dry-run   # free: preflight
```
