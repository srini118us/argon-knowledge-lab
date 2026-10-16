# Experiment 2 technical report: multistep architecture review decisions with Gemini 4 Argon and Gemini 3.8 Flash

Run date: 2026-10-16. Single run, 12 test cases, 4 configurations. All costs are usage based estimates, not billed amounts. Raw data, scoring code and offline tests are in this folder.

**Summary.** Both models, at medium thinking, made fully correct decisions on all 12 multistep cases. No configuration made an incorrect decision. High thinking added cost and latency, and all three failures occurred in the high thinking configurations. Each was an answer that never arrived rather than a wrong answer: one was a thinking budget exhausted, two were dropped connections that may reflect service conditions. In this single 12 case run, Argon at medium used the fewest tokens and had the lowest latency. Because the weaker configuration also scored 12 of 12, this benchmark shows that both models are sufficient for this task; it cannot show which reasons better.

## 1. Business problem and scenario

Enterprise architecture review boards approve or reject integrations against several documents that interact: a security policy, a data classification standard, regional rules, network standards, vendor contracts, a register of time limited waivers and a change calendar. Errors are costly in both directions: approving a non compliant integration creates audit and regulatory exposure, and rejecting a compliant one delays delivery. The question is whether a frontier model adds measurable value over a cheaper model on this kind of rule based, multistep decision.

The scenario is a synthetic Architecture Review Board at Northwind Logistics. Each case is a short prose proposal to send data to an external vendor. The model must return a decision (approve, approve with conditions, or reject), the exact rules violated or attached as conditions, and citations in the form `DOC_ID@VERSION#CLAUSE`.

## 2. Design and evaluation method

| Element | Choice |
|---|---|
| Evidence | Full policy pack of 16 documents (about 4.4K tokens) in every request; no retrieval, so only reasoning is tested |
| Reasoning demands | Classify data by its highest class; apply a stricter regional annex over the global policy; check waiver vendor, scope and validity on the go live date; ignore a superseded policy version; apply an inclusive freeze window |
| Cases | 12 test cases (2 approve, 4 approve with conditions, 6 reject) and 3 dev cases for the pilot |
| Ground truth | Computed by a rule engine from a structured policy specification and frozen before any paid call |
| Case validation | Each case tested against 20 simulated reasoning mistakes; every reject or conditions case changes outcome if any of 3 to 7 steps is skipped, and every approve case contains 2 or 3 traps that tempt over application of a rule |
| Independent check | A separate reviewer given only the pack and proposals reached the computed key on all 15 cases; ambiguous wording it flagged was fixed before freezing |
| Configurations | Flash and Argon, each at medium and high thinking; identical prompt, pack and JSON schema; 32,000 output token cap including thinking; no retries |
| Primary metric | Fully correct: decision, violation set and condition set all exact |
| Citation scoring | Citations are read only from the structured `citations` array; clauses mentioned only in the rationale text are not counted. Required citations for a case are the clauses of its violations and conditions, the waivers relied on, and the vendor contract where it determines a finding. Approve cases (T01, T07) require none. Evidence valid means fully correct and every required citation present in the array |
| Completion | Reported separately: a call that returns no usable answer is a completion failure, not a wrong decision |

## 3. Results

| Configuration | Completed | Fully correct, of completed | Fully correct, end to end | Completion failures |
|---|---|---|---|---|
| Flash, medium | 12/12 | 12/12 | 12/12 | none |
| Argon, medium | 12/12 | 12/12 | 12/12 | none |
| Argon, high | 11/12 | 11/11 | 11/12 | 1: output budget spent on thinking |
| Flash, high | 10/12 | 10/10 | 10/12 | 2: connection dropped |

Every completed answer had the exact decision, the exact violation and condition sets and all required citations in its `citations` array. No answer relied on the superseded policy, and none cited a clause that does not exist.

The citation check is informative only on the 10 cases that require citations. On the two approve cases it is met trivially: three answers there (Argon medium on T01, Flash high and Argon high on T07) left the `citations` array empty and named clauses only in the rationale, which the scoring does not count either way.

## 4. Cost, latency, tokens and completion reliability

| Configuration | Est. cost, 12 cases | Cost per fully correct case | Median latency, completed | Output plus thinking tokens per call | Completion rate |
|---|---|---|---|---|---|
| Flash, medium | $0.163 | $0.014 | 18.0 s | 2,620 | 100% |
| Argon, medium | $0.211 | $0.018 | 10.8 s | 713 | 100% |
| Argon, high | $1.267 | $0.115 | 63.7 s | 9,513 | 92% |
| Flash, high | $0.468* | $0.047 | 61.0 s | 11,476 | 83% |

\* Measured usage for the 10 calls that returned usage. The two dropped calls are reserved at worst case ($0.249) because their actual cost is unknown.

Observations:
* **Argon at medium was the most efficient configuration in this single 12 case run.** It used about 3.7 times fewer output plus thinking tokens than Flash at medium and had the lowest median latency. On 6 of 12 cases it reported zero thinking tokens and was still fully correct. Its estimated cost was about 1.3 times Flash's because its per token prices are higher. One run on one task cannot establish a stable latency or token difference; these are observations, not general properties of either model.
* **High thinking was expensive and variable.** Argon at high used between 2,571 and 31,997 thinking tokens per case; Flash at high used between 5,048 and 30,716. Compared with medium, high cost about 3.4 (Flash, per completed call) to 6.0 (Argon) times more and was about 3.4 to 5.9 times slower.
* **Experiment spend.** Measured usage across pilot, rerun and test was $2.645; the ledger total of $3.275 includes $0.630 of worst case reservations for calls that returned no usage. Billing has not yet been reconciled against these figures.

## 5. Failure case studies

**Case study 1: Argon at high thinking on T12, output budget exhausted.** T12 asks whether driver locations for EU data subjects may go to a vendor hosted in Asia Pacific. The answer is a reject on the residency rule; a waiver for missing encryption applies but is not listed on a reject. Argon at high spent 31,997 of its 32,000 token budget thinking, returned 3 output tokens and no answer, after 324 s and an estimated $0.33. Argon at medium answered the same case correctly in 7 s with zero thinking tokens. In the pilot, Argon at high also exhausted a 16,000 token budget on DEV1, an approve case with no rule failures by design. Lesson: at high thinking, the output cap is a reliability parameter, not just a cost control, and more thinking budget did not translate into better decisions on these cases.

**Case study 2: Flash at high thinking on T05, connection dropped after 54 minutes.** The request was sent with a 10 minute timeout requested through the SDK. The server disconnected after 3,247 s without a response. The SDK timeout did not bound the call, so one stalled request extended the whole run by almost an hour. The harness has since been fixed: the runner now enforces its own hard deadline and records the outcome as `timeout`. Lesson: client side deadlines must be enforced by the caller and tested; a configuration value is not evidence that a timeout works.

**Case study 3: Flash at high thinking on T12, connection dropped after 272 s.** A second disconnect on the same arm, with no usage returned, so its cost is unknown and reserved at worst case. One run cannot separate a configuration effect (long high thinking calls) from service conditions on the day. Lesson: completion failures need their own metric and their own retry policy; folding them into accuracy would have reported Flash at high as making two wrong decisions when it made none.

## 6. Limitations and lessons learned

Limitations:
* **Ceiling effect.** With the weaker configuration at 12 of 12, the benchmark cannot rank the models on reasoning. The pilot predicted this (Flash at medium scored 3 of 3 on dev cases), and the planned step to harden the dev cases was skipped.
* One synthetic policy pack with crisp rules; real policy ambiguity is not tested.
* 12 cases and one trial; latency and token differences are observations from one run, not stable estimates.
* High thinking results depend on the 32,000 token cap and on service conditions on the day.
* Costs are estimates from usage fields; billing reconciliation is pending.
* The citation check is trivially met on the 2 approve cases, so evidence validity is informative on 10 of 12 cases.

Lessons:
1. Calibrate difficulty on dev cases before freezing, and act on the calibration rule.
2. Report completion and correctness separately.
3. Enforce deadlines in the harness and test them offline.
4. Treat the output cap as part of the configuration under test when thinking is enabled.
5. Keep a ledger that separates measured usage from worst case reservations.

## 7. Implications for enterprise model selection

For rule based review tasks of this size, where the full policy context fits in the prompt and the rules are explicit:
* **Start with medium thinking.** In this run it was fully accurate, fully reliable, cheaper and faster than high thinking for both models.
* **Choose between the two models on efficiency and operations rather than accuracy:** Flash had the lowest estimated cost; in this single run Argon at medium had the lowest latency and token use, which would need repeated runs to confirm. The difference in cost per decision (about $0.014 against $0.018) is small next to the cost of a review board's time.
* **Do not assume high thinking improves rule application.** Here it added cost and latency with no accuracy gain, and all completion failures occurred at high thinking.
* **Test on harder material before attributing value to a frontier model.** This benchmark establishes sufficiency, not superiority. A fair test of reasoning strength needs cases on which the cheaper configuration fails.

## 8. Experiment 1 and Experiment 2 compared

| | Experiment 1 | Experiment 2 |
|---|---|---|
| Question | Which retrieval design gives the best accuracy and cost? | With all evidence in context, does Argon make better multistep decisions? |
| Task | 50 questions over a 47K token architecture corpus, including diagrams | 12 integration proposals against a 4.4K token policy pack |
| What was varied | Long context, agentic retrieval, RAG with captions, text RAG; both models at medium | Both models at medium and high thinking; no retrieval |
| Accuracy result | Long context 50/50 for both models. Flash missed 9, 4 and 2 questions in text RAG, RAG with captions and agentic retrieval. Argon missed the same questions in both RAG variants; in agentic retrieval it answered one diagram question (D01) that Flash missed | Medium 12/12 for both models; no incorrect decisions in any configuration |
| Where the configurations differed | Cost: Flash about one sixth of Argon in long context; one agentic question | In this single run, Argon medium fastest with the fewest tokens; high thinking costlier, slower and less reliable |
| Main limitation | Single run, synthetic corpus, retrieval settings untuned | Ceiling effect, single run, crisp synthetic rules |
| Combined reading | Flash did fail questions in Experiment 1, mostly where the retrieval step had not supplied the evidence, and Argon failed the same ones with a single exception (D01 in agentic retrieval). In Experiment 2 neither model made an incorrect decision. Across both experiments the two models' errors were almost entirely shared, and Argon cost more (about 6.4 times Flash in Experiment 1 long context, about 1.3 times at medium in Experiment 2). Its measured advantages were one agentic question in Experiment 1 and, in this single run, lower latency and token use at medium thinking in Experiment 2. Neither experiment included enough cases where the models diverged to establish a difference in reasoning strength. | |
