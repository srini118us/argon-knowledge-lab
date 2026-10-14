# Architecture Knowledge Assistant: Evaluation Plan

**Research question:** When should an enterprise AI architect choose classic RAG, long context inference, or agentic retrieval?

Status date: 2026-10-13. Status: DRAFT for approval. No evaluation run has happened. Nothing here assumes long context beats RAG.

## 1. Story (six chapters)

1. Classic RAG answers the new architect's simple questions, then meets cross document questions.
2. Argon with the whole corpus in context: accuracy, then real cost and latency.
3. Caching: savings only where `total_cached_tokens` shows them.
4. Argon as an agent searching through tools: the middle path.
5. Gemini 3.8 Flash on the same tests: where it is enough.
6. Decision table: which design and which model for which situation.

## 2. Verified so far (saved result files)

| Capability | Status |
|---|---|
| `gemini-4-argon` via Interactions API | VERIFIED (access test) |
| Native function calling on Argon, parallel calls | VERIFIED (probe P4: 3 parallel tool calls, correct arguments, correct amounts) |
| `gemini-3.8-flash` callable on the same key | VERIFIED (probe P1) |
| File Search tool on Argon | VERIFIED (probe P6, 2026-10-13): `file_search_call` steps, correct answer, `file_citation` annotations. Not yet in Google's File Search model list. Combined with custom functions: not tested |
| Implicit caching on Argon | UNRELIABLE (P7, P7b, P7c, 2026-10-13, 21 requests with an identical ~11.4K token corpus): **stateless** resend: 0 of 11 hits. **Chained** via `previous_interaction_id`: 2 of 3 hits (~82%). **Branched** from one corpus loading interaction: 1 of 7 hits (9,326 tokens); the other 6 reported only 22 cached tokens, also seen on the very first request. Server held history is still billed as input. Latency 3 to 51 s, not correlated with hits. Budget assumes no cache savings |
| Image content inside a function result (needed for the agent arm on diagrams) | NOT TESTED; agent arm uses frozen captions unless verified |

## 3. Arms (identical inputs, prompts and answer format across arms)

| Arm | What the model sees | Retrieval |
|---|---|---|
| R1 Classic RAG, text only | Top 8 chunks for the question | Section aware chunking (about 800 tokens, 100 overlap), `gemini-embedding-2`, cosine top k. Labelled text only: diagrams excluded |
| R2 Classic RAG plus captions | Same as R1, diagram captions indexed as text | Captions generated once by Gemini 3.8 Flash from each PNG, frozen and published |
| L Long context | Entire corpus, diagrams as images, fixed order, question last | None. Corpus first so a stable prefix can be cached |
| A Agentic retrieval | Question only, plus tools | `search_docs(query, k)` on the R2 index, `read_doc(doc_id, section)`, `list_docs(type, system)`; at most 8 rounds |
| F File Search (only if P6 passes on Argon) | Google managed retrieval | Optional arm, reported separately |

Fairness rules:
* Same embedding index for R1, R2 and A. Chunk size and k are tuned once on a **separate 10 question dev set**, never on the 50 test questions.
* One system prompt and one answer schema for every arm: `{status: answered | not_found, answer, citations: [doc_id@version §section]}`.
* Visual questions are scored separately, so text only RAG is never silently penalized.
* Argon and Flash use identical arms, prompts and data; thinking levels as listed in the matrix.

## 4. Corpus design

Synthetic company **Northwind Logistics**: an order management platform with about 12 services, an event bus, 4 external integrations (carrier API, payment gateway, CRM, ERP), and a data platform. Generic enterprise, not SAP specific.

| Document type | Small (≈40K tokens) | Large (≈500K tokens) |
|---|---|---|
| Architecture decision records (some superseded, explicitly or only by a later date) | 8 | 60 |
| Integration and API specs (v1 and v2 coexisting) | 5 | 40 |
| Vendor contracts and SLAs | 3 | 15 |
| Runbooks and incident postmortems | 4 | 50 |
| Policies (data retention, security, change management) | 3 | 20 |
| Architecture and sequence diagrams (PNG, rendered from source) | 4 | 20 |
| Irrelevant material (meeting notes, unrelated projects, HR notices) | 5 | 120 |

Design rules:
* **Fact base first.** A structured fact file (services, owners, versions, limits, dates, dependencies) is written before any prose. Documents are generated from it, and ground truth comes from it, never from model output.
* **Genuine dependencies:** for example a retry limit in a runbook depends on a rate limit in a vendor contract, which was changed by a later ADR.
* **Realistic noise, no sabotage:** documents use normal headings and vocabulary. No deliberately misleading keywords aimed at embeddings.
* **Same 50 questions at every size.** The large corpus adds documents but never changes an answer, so accuracy against size is a clean measurement.
* Authored with Claude, a different vendor from the models under test, which avoids a model grading its own family's writing. Stated as a limitation anyway.

## 5. Question set (50 test, frozen before any test run, plus 10 dev)

| Category | Count | Example shape | Ground truth |
|---|---|---|---|
| Single fact | 12 | Which service owns order cancellation? | One value plus one citation |
| Cross document | 12 | What is the effective carrier retry limit, given the contract and the latest ADR? | Value plus all required citations |
| Conflicting versions | 10 | Which message broker is current? | Latest valid version; citing a superseded doc is an error |
| Diagram interpretation | 8 | Which service calls the payment gateway synchronously? | Answer exists only in a diagram |
| Unanswerable | 8 | What is the disaster recovery RPO for the CRM integration? | `not_found`; any value is a hallucination |

Freeze: questions, answer keys, required citations and the corpus SHA256 manifest go into one commit before the first test run. The commit ID is published.

## 6. Metrics and scoring (deterministic; no model grades another model)

| Metric | Definition |
|---|---|
| Answer accuracy | Every key fact in the answer key matched (normalized string, number or ID match) |
| Evidence correctness | Citation precision and recall against required `doc_id@version` |
| Superseded citation rate | Citations to a version that ground truth marks as superseded |
| Abstention quality | Correct `not_found` on unanswerable; false `not_found` rate on answerable |
| Retrieval recall | R1, R2, A: required sections present in what was retrieved or read |
| Thinking tokens, latency, tool calls | From API usage and timings |
| Cache hits | `total_cached_tokens` only; no hit is claimed without it |
| Cost | `pricing.py` on reported usage, plus embedding cost |

Anything the deterministic scorer cannot decide goes to a published manual review list.

## 7. Matrix and budget

Estimates use verified introductory pricing (Argon $2 in, $10 out, $0.10 cached; Flash $0.75, $3.75, $0.075) and assumed output of 1K, 3K and 6K tokens at low, medium and high thinking. The pilot replaces every assumption with measured usage. Ranges show 0% to 90% cache hits on the long context arm, which is only a scenario until measured.

| Stage | Corpus | Questions | Configs | Trials | Est. cost |
|---|---|---|---|---|---|
| 0 Probes P6, P7 | none | none | Argon | 1 | <$0.10 |
| 1 Pilot | 40K | 10 dev | R2, L, A x Argon, Flash, medium | 1 | ~$4 |
| 2 Core | 40K | 50 | R1, R2, L, A x Argon, Flash, medium | 2 | $25 to $35 |
| 3 Thinking sweep | 40K | 50 | L and A, Argon, low and high | 1 | ~$23 |
| 4 Scale | 150K | 50 | R2, L, A x both, medium | 1 | $15 to $33 |
| 5 Scale | 500K | 20 subset | R2, L, A x both, medium | 1 | $14 to $32 |
| **Total** | | | | | **≈ $80 to $125** |

**Lean option (≈ $35 to $45):** Stage 2 with 1 trial instead of 2, the thinking sweep on 20 questions, and only the 150K scale step on 20 questions (no 500K). It still supports every chapter of the story; it gives less variance information and no 500K data point.

A full factorial at every size would cost about $400, which is why stages 3 to 5 are narrowed. Each stage runs only after the previous one is reviewed, with a spend cap set on the API project. Argon rates double on 2026-12-01, so stages 2 to 5 should finish before then.

## 8. Limitations (published)

1. One synthetic corpus and 50 questions: descriptive results, not general claims.
2. Retrieval choices (chunking, k, embedding model) affect RAG results; they are fixed on the dev set and published.
3. Captions for R2 come from Flash, so R2 inherits Flash's diagram reading.
4. Cache behavior is not guaranteed by Google; results reflect our runs on our dates.
5. Interactions API caps responses at about 64K tokens; Long Decode is not tested.
6. Corpus written by Claude; models may answer differently on human written documents.

## 10. Corpus and question set status (2026-10-13)

* Small corpus built: 31 text documents (6 deliberately irrelevant), 4 PNG diagrams rendered from Graphviz source, about 47K text tokens (characters / 4; exact count comes from the API in the pilot).
* `corpus/spec/questions.json`: 50 test questions (12 single fact, 12 cross document, 10 conflicting versions, 8 diagram, 8 unanswerable) and 10 dev questions.
* `corpus/check_corpus.py small`: 0 key fact problems, 0 forbidden hits. Every answer key fact is present in its required documents; diagram only facts and unanswerable facts are absent from all text documents.
* Diagram sources (`corpus/spec/diagram_src`) are ground truth only and are never sent to a model.
* SHA256 of every file is in `corpus/small/MANIFEST.json`. The freeze becomes official at the first git commit, before the pilot.
* Documents were written by Claude subagents from the spec; hard facts were constrained to the spec, prose was free.

## 9. Next steps

1. Run P6 and P7 on the laptop; record results here.
2. Write the fact base and the small corpus; draft the 50 test and 10 dev questions; freeze.
3. Stage 1 pilot; replace estimates with measured usage; review before Stage 2.
