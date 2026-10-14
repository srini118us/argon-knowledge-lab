# Medium article outline (measured findings only)

**Working title:** Where Gemini 4 Argon Earns Its Price, and Where Flash Is Enough: Long Context vs RAG vs Agents on 50 Architecture Questions

**One sentence thesis:** On a realistic 47K token architecture corpus, long context was the most accurate design for both models, Gemini 3.8 Flash matched Gemini 4 Argon at about one sixth of the cost, and RAG's weaknesses came from retrieval rather than the model.

## 1. The question every architect gets asked
* A new architect joins and asks 50 questions across decision records, contracts, runbooks and diagrams.
* Three designs: classic RAG, long context, agentic retrieval. Two models: Gemini 4 Argon (launched 2026-10-13) and Gemini 3.8 Flash.
* Promise of the article: measured results, including our own bug.

## 2. How the test was built (credibility section)
* Synthetic company, fact base first, 50 questions frozen in a git commit before any run (b9b8bbb).
* Five question types; deterministic scoring; no model grades another model.
* Three accuracy views, all from the same raw data: answer accuracy (original), evidence valid accuracy (also requires every required current citation), and accuracy on the 42 answerable questions reported apart from the 8 correct abstentions.
* Image access is not equal: long context sends the PNGs; RAG with captions and the agent read Flash written captions; text RAG has no diagram access. Only long context tests Argon's own vision.
* Offline test suite (25 tests) reproduces the published scores from the raw JSONL.

## 3. Chapter 1: Classic RAG
* 82% for both models (33 of 42 answerable, 8 of 8 abstentions); 0 of 8 diagram questions by design; identical errors across models.
* X07 missed in every RAG cell because POL-SEC-01@v2 was not retrieved.
* Lesson: the retriever sets the ceiling, not the model. Recall is reported at document level only.

## 4. Chapter 2: Everything in context
* 100% for both models, including all diagram questions read directly from images.
* Estimated cost from usage fields: Argon $0.091 per question vs Flash $0.014 (not yet reconciled with billing).

## 5. Chapter 3: What caching actually saved
* Flash: 1.6M cached tokens, cost per question fell to about $0.006 on most questions.
* Argon: 44K cached tokens in the same pattern; probes showed hits mainly in server held conversation chains.
* Careful wording: our requests, our dates, best effort caching.

## 6. Chapter 4: Agentic retrieval
* 96% Flash, 98% Argon by the original score; 98% and 100% after one documented review (C05: the frozen pattern rejected the singular "8 second timeout"). Show both, never only the reviewed number.
* Slowest design (about 20 to 24 s); much cheaper than long context.
* Tool logs: Argon read whole documents more (read_doc 3.42 vs 2.42 per question) and searched less (1.26 vs 2.24), which explains its 16K vs 2.9K input tokens.
* Diagrams here are Flash captions, not images.

## 7. Chapter 5: Where Flash was enough, and where Argon differed
* Equal accuracy in long context and both RAG variants; Argon one question better as an agent.
* Argon cited superseded document versions more often (16 cases across all cells, 12 of them Argon), but every one also cited the current version: historical reference, 0 cases of outdated authority, no effect on correctness. Frame as citation hygiene, not an error.

## 8. The bug that almost became a finding
* Embedding index with 2 vectors for 86 chunks; RAG looked useless in the first pilot.
* The fix, the rerun of only affected arms, and the rule: check one vector per chunk before trusting a RAG benchmark.

## 9. Decision table for architects (from this data only)
| Situation in this experiment | What worked best |
|---|---|
| Corpus fits comfortably in context, accuracy first | Long context with Gemini 3.8 Flash |
| Cost or latency first, text answers | RAG with Flash (82 to 92%, about $0.005 per question, about 5 to 6 s) |
| Diagrams matter but full context is not an option | Captions or agentic retrieval |
| Audit trail must cite only current versions | Check citations for superseded documents regardless of model (here all were historical, alongside the current version) |

## 10. Limits and what comes next
* One corpus, 50 questions, one run, medium thinking only, 47K tokens: not a long context stress test.
* Scorer limits: regex patterns (one known false negative, C05); D08 corpus wording invited over inference.
* Budget guardrail checks before each question, excludes embeddings, and records failed requests at $0.
* Next: the same 50 questions at 150K and 500K tokens, where long context cost grows linearly and RAG cost does not.
* Billing reconciliation note: all costs are usage based estimates from API usage fields, pending reconciliation (about $10.60 estimated vs about $25 seen). Embeddings (about 172K estimated tokens) are reported separately and not priced.

## Assets to prepare
* Results table (README section 1), publication metrics (section 1b), image access table (section 3), category table (section 6), caching chart (cost per question by question number for L Flash vs L Argon), architecture diagram of the four arms.
* Links: repository, freeze commit, raw JSONL.
