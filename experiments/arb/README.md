# Experiment 2: Architecture Review Board decisions

**Question:** when all the evidence is in context, does Gemini 4 Argon make better multistep architecture decisions than Gemini 3.8 Flash, and does high thinking change the answer?

Status: **closed.** Run once on 2026-10-16 (12 test cases x 4 arms); no further paid runs are planned. Experiment 1 (repository root) is unchanged. The full write up is in `REPORT.md`.

## Results (single run, 12 test cases)

Run file: `results/runs/test_20261016_152247.jsonl`, scored by `score_arb.py` (offline test `test_published_experiment2_results_reproduce` reproduces every number below). Costs are usage based estimates, not billed amounts.

**Correctness and completion are reported separately.** A call that never returned a usable answer is a completion failure, not a wrong decision.

| Arm | Completed | Fully correct, of completed | Fully correct, end to end | Completion failures | Est. cost* | Median latency, completed | Output plus thinking per call** |
|---|---|---|---|---|---|---|---|
| Flash, medium | 12/12 | 12/12 | 12/12 | none | $0.163 | 18.0 s | 2,620 |
| Argon, medium | 12/12 | 12/12 | 12/12 | none | $0.212 | 10.8 s | 713 |
| Argon, high | 11/12 | 11/11 | 11/12 | T12 budget exhausted | $1.267 | 63.7 s | 9,513 |
| Flash, high | 10/12 | 10/10 | 10/12 | T05, T12 connection dropped | $0.468 | 61.0 s | 11,476 |

\* Measured usage only. Flash high's two dropped calls returned no usage; the ledger reserves $0.249 for them at worst case.
\** Mean over calls that returned usage (12, 12, 12 and 10). Argon high includes the T12 call that spent 31,997 tokens thinking.

Every completed answer in every arm was fully correct: exact decision, exact violation and condition sets, all required citations, no reliance on the superseded policy, and no citations to clauses that do not exist. **There were no incorrect architecture decisions.** The three misses are answers that never arrived:

| Case | Arm | Cause | Latency |
|---|---|---|---|
| T05 | Flash, high | Server disconnected without a response | 3,247 s |
| T12 | Flash, high | Server disconnected without a response | 272 s |
| T12 | Argon, high | 31,997 thinking tokens and 3 output tokens: the 32,000 cap went to thinking | 324 s |

### Findings (this run only)

1. **No accuracy difference.** Both medium arms were fully correct on all 12 cases, and every completed answer from the high arms was also correct. The rule fixed before the run (repeat only if two arms differ by 3 or more fully correct cases) is not triggered.
2. **Argon at medium was the most efficient arm here:** about 3.7 times fewer output plus thinking tokens than Flash at medium (713 against 2,620) and the lowest median latency (10.8 s against 18.0 s), at about 1.3 times Flash's estimated cost ($0.212 against $0.163). This is one run on one task; it is not evidence that Argon is generally faster.
3. **High thinking added cost and latency without improving accuracy, and all completion failures occurred there.** Compared with medium it cost about 3.4 (Flash, per completed call) to 6.0 (Argon) times more and was about 3.4 to 5.9 times slower. One failure was a thinking budget exhausted (Argon T12); the two Flash failures were dropped connections that may reflect service conditions.
4. **The benchmark hit a ceiling.** See "Why the ceiling means no ranking" below.

### Why the ceiling means no ranking

When the weaker configuration already scores 12 of 12, the test has no room to show that another configuration reasons better. Both models could differ substantially on harder problems and this benchmark would still report a tie. The ceiling was foreseeable: the pilot scored Flash at medium 3 of 3 on the dev cases, and the plan said to harden the dev cases in that situation; that step was skipped (a deviation from the plan, recorded here). The design did force multistep reasoning (each case needs 3 to 7 steps, checked by mutation), but the rules were crisp and the pack short, so the reasoning required was within both models' reach at medium thinking. **The result supports "both are sufficient for this task", not "they reason equally well".**

### Harness defects found during the run, and fixes

* **Timeout not enforced (fixed after the run).** `HttpOptions.timeout` did not bound a long running Interactions call: T05 ran 54 minutes. The runner now enforces a hard deadline itself (`call_with_deadline`, a daemon thread with a join timeout, 600 s). An abandoned call cannot be cancelled on the server and is charged at worst case. Covered by offline tests in `tests/test_harness.py`.
* **Completion status (added after the run).** Every row now carries `status` (completed, budget_exhausted, parse_error, timeout, connection_error, api_error); rows from 2026-10-16 are classified from their error and usage fields. Scoring reports accuracy on completed responses and end to end separately.
* **Token and latency means (corrected after the run).** The first scoring pass averaged failed calls as zero tokens and included their latency; means now use calls that returned usage, and median latency uses completed responses. This changed Flash high's figures (9,563 to 11,476 tokens; 72 s to 61 s); correctness figures are unchanged.
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

> The team proposes to send delivery addresses to Parcelytics. Any people the data is about are in the US and the EU. ... Data is transferred over standard HTTPS (server side TLS). Parcelytics will retain the data for 20 days. ... Planned production go live: 2026-11-05.

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

Identical system prompt, pack, proposal text and JSON schema for every arm; pack first and proposal last; `max_output_tokens` 32,000 (includes thinking); no tools; no client retries; a 600 s timeout requested through the SDK (in the test run this was not enforced; the runner now adds its own hard deadline); cases run in case major order so every arm answers the same cases even if the cap stops the run.

| Arm | Model | Thinking |
|---|---|---|
| 1 | gemini-3.8-flash | medium |
| 2 | gemini-3.8-flash | high |
| 3 | gemini-4-argon | medium |
| 4 | gemini-4-argon | high |

## Pilot findings (2026-10-16, dev cases)

* Earlier attempts failed with 503 and 429 errors from a key on a free tier project; no tokens were processed. The guard booked them at worst case ($0.38 in the ledger, not real spend).
* With a billed key, 10 of the 12 planned calls were made before the guard stopped the run; 9 completed and parsed, and all 9 decisions matched the key. Measured output plus thinking per case: 0.5K to 2.6K at medium (Argon 497 to 934, Flash 1,785 to 2,602); 4.2K to 13.1K for Flash at high (mean about 10K).
* Argon at high thinking on DEV1 used 15,997 thinking tokens and 3 output tokens, exactly the 16,000 cap, and returned no answer. The cap is honoured and includes thinking. The guard stopped the run because actual cost beat the worst case by $0.001: the input estimate (characters / 4) was 4,673 tokens against 5,241 actual, about 11% low.
* Changes after the pilot: cap raised to 32,000 for all arms; input estimate margin 1.25; client retries off with a 10 minute SDK timeout (later found not to be enforced); case major order; an `--arms` filter for single arm reruns.
* Pilot scores (fully correct): Flash medium 3/3, Flash high 3/3, Argon medium 3/3; Argon high 0/1 on the 16K cap (budget exhausted), then 1/1 on the 32K rerun.

## Cost: estimates, ledger and billing

All figures are usage based estimates (tokens from API usage fields times published prices). None is a confirmed billed amount.

**Preflight versus actual (test run):** preflight expected about $4.02 (assuming 20,000 output plus thinking tokens per high call); measured usage was $2.110 because high calls averaged 9,500 to 11,500 tokens.

**Ledger reconciliation** (`results/ledger.jsonl`, 65 entries, $3.275 in total):

| Component | Calls | Amount | Basis |
|---|---|---|---|
| Pilot, billed key (dev cases) | 10 | $0.386 | measured |
| DEV1 rerun, Argon high | 1 | $0.149 | measured |
| Test run, completed or budget exhausted | 46 | $2.110 | measured |
| **Measured total** | **57** | **$2.645** | |
| Free tier key errors (503, 429) | 6 | $0.381 | worst case reservation; free tier calls are not billed, so most likely $0 |
| Test run, connection dropped (Flash high T05, T12) | 2 | $0.249 | worst case reservation; actual unknown |
| **Ledger total** | **65** | **$3.275** | |

The 57 measured entries match the run files one to one by interaction ID. Two run files contain no successful calls (`dev_20261016_123402`, `dev_20261016_134538`), and one has a header but no rows (`dev_20261016_135843`, interrupted while the client retried a free tier limit).

**Billing:** not yet reconciled. The billing account showed $19.56 for October before this experiment and is shared by four projects. The experiment should add about $2.65 to $2.90 (measured usage plus up to the dropped calls). The check is the October cost per model for the billed project after the run, compared with the measured figures above.

**Guard:** before every call, the ledger total plus that call's worst case (input estimate with a 1.25 margin plus 32,000 output tokens at the output rate) must stay within `--cap`, or the run stops. The ledger persists across runs, so the $5 cap covered pilot and test together; the run finished at $3.275 in the ledger. Calls without usage are charged at worst case.

## Plan and what happened

1. **Pilot** on 3 dev cases: done. Fixes followed (output cap, estimate margin, retries off). The plan's step "if Flash at medium is perfect on dev, harden the dev cases" was **not** carried out; see the ceiling section.
2. **Freeze commit** of pack, cases, key and runner before the test run: done (commits `5034ca4` and `aebe620`).
3. **Test run**, 12 cases x 4 arms: done, $2.110 measured.
4. **Repeated trials:** not triggered (no two arms differ by 3 or more fully correct cases). The experiment is closed.

## Limitations

* One synthetic policy pack written by the experimenter; the rules are deliberately crisp, so real policy ambiguity is not tested.
* 12 test cases, one trial: descriptive only.
* The pack is short (about 4.4K tokens), so this tests reasoning, not long context.
* Ceiling effect: medium arms were perfect, so the experiment cannot rank the models on accuracy.
* High thinking results depend on the 32K output cap; a larger cap might have let Argon finish T12.
* Flash high's two dropped connections may reflect service conditions on the day rather than the configuration; one run cannot tell.
* Different tokenizers: the same prompt counted as about 5,000 input tokens for Flash and 5,244 for Argon.

## Commands

```powershell
.\.venv\Scripts\python.exe experiments\arb\check_cases.py                       # free: validate cases and key
.\.venv\Scripts\python.exe -m pytest -q                                         # free: all offline tests
.\.venv\Scripts\python.exe experiments\arb\run_arb.py --split dev --cap 5 --dry-run   # free: preflight
```
