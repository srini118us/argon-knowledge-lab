# Architecture Knowledge Assistant: Long Context vs RAG vs Agentic Retrieval on Gemini 4 Argon

**Research question:** when should an enterprise AI architect choose classic RAG, long context inference, or agentic retrieval?

This lab answers that question for one realistic setting: a new architect asking 50 questions about a synthetic company's architecture documentation (about 47K tokens). It compares four retrieval designs on `gemini-4-argon` and `gemini-3.8-flash`, scores every answer deterministically against a frozen answer key, and reports cost, latency and caching from API usage fields.

Status: main benchmark complete (2026-10-14). No further paid runs have been made since. Results apply to this corpus and these dates only.

## 1. Headline results (main benchmark, valid)

Run file: `results/runs/test_20261013_235517.jsonl`. Scores: `results/scores/test_20261013_235517_summary.csv`. One execution, medium thinking level, 50 test questions, 400 model runs, total logged cost **$8.31**.

| Approach | Model | Accuracy (of 50) | Total cost | Cost per question | Mean latency | Cached input tokens (total) | Superseded citations* |
|---|---|---|---|---|---|---|---|
| Long context | Gemini 3.8 Flash | **50 (100%)** | $0.71 | $0.014 | 6.6 s | 1,614,299 | 0 of 42 |
| Long context | Gemini 4 Argon | **50 (100%)** | $4.56 | $0.091 | 9.2 s | 44,075 | 3 of 42 |
| Agentic retrieval | Gemini 3.8 Flash | 48 (96%) | $0.23 | $0.005 | 20.1 s | 325 | 2 of 42 |
| Agentic retrieval | Gemini 4 Argon | 49 (98%) | $1.34 | $0.027 | 23.9 s | 256,559 | 3 of 42 |
| RAG with diagram captions | Gemini 3.8 Flash | 46 (92%) | $0.25 | $0.005 | 6.1 s | 2,531 | 1 of 42 |
| RAG with diagram captions | Gemini 4 Argon | 46 (92%) | $0.43 | $0.009 | 12.7 s | 66,483 | 2 of 42 |
| Classic RAG, text only | Gemini 3.8 Flash | 41 (82%) | $0.25 | $0.005 | 5.0 s | 0 | 1 of 42 |
| Classic RAG, text only | Gemini 4 Argon | 41 (82%) | $0.56 | $0.011 | 6.0 s | 0 | 4 of 42 |

\* Answers to the 42 answerable questions whose citations include a document version that the answer key marks as superseded. The answer itself may still be correct.

Unanswerable questions: every approach and both models answered `not_found` on all 8 (no hallucinated values).

**Token usage per question (means from API usage fields; `results/analysis/test_20261013_235517_results_table.md`):**

| Approach | Model | Input tokens | Output tokens | Thinking tokens | Share of input cached | Median latency | Tool calls |
|---|---|---|---|---|---|---|---|
| Long context | Flash | 45,633 | 71 | 390 | 71% | 5.9 s | 0 |
| Long context | Argon | 45,556 | 95 | 73 | 2% | 7.1 s | 0 |
| Agentic retrieval | Flash | 2,889 | 205 | 456 | 0% | 18.9 s | 5.3 |
| Agentic retrieval | Argon | 16,325 | 229 | 161 | 31% | 18.8 s | 5.4 |
| RAG with captions | Flash | 4,782 | 73 | 290 | 1% | 5.1 s | 0 |
| RAG with captions | Argon | 4,913 | 104 | 20 | 27% | 4.7 s | 0 |
| Text RAG | Flash | 4,789 | 73 | 303 | 0% | 4.8 s | 0 |
| Text RAG | Argon | 4,922 | 101 | 26 | 0% | 4.9 s | 0 |

Cost check: Argon long context, 45,556 input tokens at $2 per million plus about 170 output and thinking tokens at $10 per million gives about $0.093, against $0.091 logged (the difference is the few cached tokens). The cost formula is consistent with the usage fields.

## 2. Findings (measured, this experiment only)

1. **At about 47K tokens, long context was the most accurate approach for both models (100%).** Gemini 3.8 Flash matched Gemini 4 Argon's accuracy at about one sixth of the cost ($0.71 vs $4.56).
2. **Retrieval, not the model, limited RAG.** Argon and Flash produced identical accuracy in every question category under both RAG variants. The misses came from what the index did or did not return.
3. **Diagrams need an explicit path into text RAG.** Text only RAG answered 0 of 8 diagram questions (correctly abstaining on 7, one incorrect answer). Adding frozen captions raised this to 5 of 8; long context, which sees the images directly, answered 8 of 8.
4. **Agentic retrieval closed most of the gap to long context** (96% Flash, 98% Argon) at a fraction of long context cost, but was the slowest approach (about 20 to 24 s per question).
5. **Argon cited superseded document versions more often than Flash** in all four approaches (3 vs 0, 3 vs 2, 2 vs 1, 4 vs 1 of 42). A superseded citation does not by itself mean a wrong answer; each case, with its answer, is listed in the error report. This affects audit quality.
6. **Caching behaved very differently** (section 5): 71% of Flash's long context input was served from cache, 2% of Argon's.
7. **At the medium thinking level, Flash used more thinking tokens than Argon** in every approach (for example 390 vs 73 per question in long context, 290 vs 20 in RAG with captions). Argon's higher cost came from its input price and missed caching, not from thinking.
8. **As agents, the two models explored differently:** both made about 5.4 tool calls per question, but Argon took in about 16K input tokens per question against Flash's 2.9K, possibly because Argon read whole documents where Flash relied more on search snippets; this explanation is not yet verified against the tool call logs in the raw JSONL.
9. **Mean latency hides outliers:** Argon RAG with captions averaged 12.7 s but its median was 4.7 s, so a few slow requests dominate the mean. Medians are reported alongside means.

## 3. The four approaches

All four use the same system prompt, the same answer schema (`status`, `answer`, `citations` as `DOC_ID@VERSION`) and the same questions. Code: `src/argon_lab/arms.py`.

* **Long context (L):** every document, plus the four diagram PNGs as images, is sent with each question. The corpus comes first in a fixed order and the question last, so a cache could reuse the prefix. No retrieval step.
* **Classic RAG, text only (R1):** documents are split into section aware chunks of about 800 tokens, embedded once with `gemini-embedding-2`, and the 8 most similar chunks are sent with the question. Diagrams are not indexed, so diagram answers are out of reach by design.
* **RAG with diagram captions (R2):** the same as R1, plus a text caption of each diagram, generated once by Gemini 3.8 Flash from the PNG and frozen in `corpus/small/captions/` before the run. This is the fair visual comparison for text RAG; it inherits Flash's reading of the diagrams.
* **Agentic retrieval (A):** the model gets only the question and three read only tools: `list_docs`, `search_docs` (the R2 index) and `read_doc`. It decides what to search and read, for at most 8 rounds. Diagrams are available to it through their captions.

## 4. Corpus and questions

* Synthetic company Northwind Logistics: 31 text documents (decision records, API specs, contracts, runbooks, postmortems, policies, service catalogs, and 6 deliberately irrelevant documents) plus 4 diagrams. About 47K text tokens.
* Documents were generated from a structured fact base (`corpus/spec/corpus_spec.json`); answers come from the fact base, never from model output.
* 50 test questions in five categories: single fact (12), cross document (12), conflicting versions (10), diagram (8), unanswerable (8). Plus 10 separate dev questions used only for the pilot.
* `corpus/check_corpus.py` verifies that every answer key fact exists in its cited documents, and that diagram only facts and unanswerable facts appear in no text document (0 problems at freeze).
* Freeze commits: corpus and questions **b9b8bbb**, line endings **fb2b5da**, runner and frozen captions **e10ac9c**, results **07e6f58**.

## 5. Caching: what we observed

These observations cover our requests on 2026-10-13 and 2026-10-14 only. Google documents implicit caching as best effort with no guarantee, and the behavior may differ at other times or volumes.

* **Probes, Argon, identical ~11.4K token prefix, 21 requests:** resending the full prefix each time: 0 of 11 substantial hits. A conversation chain held on the server (`previous_interaction_id`): 2 of 3 hits. Branching every question from one corpus loading interaction: 1 of 7 hits.
* **Main benchmark, long context (about 52K token prefix, 50 requests each):** Flash reported 1,614,299 cached tokens and its per question cost fell from about $0.035 to about $0.006 on most questions. Argon reported 44,075 cached tokens; its cost stayed at about $0.092 per question except one question ($0.010).
* Argon's agentic runs reported 256,559 cached tokens, which fits the probe finding that Argon cached within server held conversation chains.
* No caching savings are claimed beyond what `total_cached_tokens` reports.

## 6. Error analysis by category

| Category | Long context | Agentic | RAG with captions | Text RAG |
|---|---|---|---|---|
| Single fact (12) | 12 / 12 both | 12 / 12 both | 12 / 12 both | 12 / 12 both |
| Cross document (12) | 12 / 12 both | 12 / 12 both | 11 / 12 both | 11 / 12 both |
| Conflicting versions (10) | 10 / 10 both | 9 / 10 both | 10 / 10 both | 10 / 10 both |
| Diagram (8) | 8 / 8 both | Argon 8, Flash 7 | 5 / 8 both | 0 / 8 both |
| Unanswerable (8) | 8 / 8 both | 8 / 8 both | 8 / 8 both | 8 / 8 both |

What the run logs show directly:
* **Diagrams, RAG with captions:** both models answered `not_found` on D01 (sync or async call to PayNimbus) and D02 (Kafka topic between shipping and carrier services), whose answers are in the DIAG-01 caption. This points to the caption chunk not ranking in the top 8 for those questions. A third diagram answer was incorrect.
* **Diagrams, text RAG:** both models abstained on 7 of 8 and gave an incorrect answer to D08, which no text document supports.
* **Diagrams, agentic Flash:** answered `not_found` on D01.
* **Cross document (both RAG variants) and conflicting versions (agentic):** one question each, identical across models. The specific question IDs, the models' answers and their citations are listed by `analyze_results.py` in `results/analysis/test_20261013_235517_error_report.md`.

## 7. The retrieval bug in the pilot (invalid results, kept on purpose)

* **What happened:** in the first pilot (`results/runs/dev_20261013_224947.jsonl`), the index held **2 vectors for 86 chunks** (verified: array shape `(2, 3072)`). `gemini-embedding-2` returned one vector per batch when given a plain list of strings, so retrieval returned almost nothing. RAG with captions answered `not_found` on nearly every dev question, and the agent's search tool was affected the same way.
* **Correction:** `retrieval.py` now sends each text as its own content item, verifies one vector per chunk, falls back to one call per text, and rebuilds any cache with the wrong count. Committed separately as "Fix: one embedding per chunk".
* **Why only two arms were rerun:** only RAG and the agent use the index. Long context never touches it, so its pilot results were already valid. The rerun (`results/runs/dev_20261013_234055.jsonl`, $0.40) gave 10 of 10 for every arm and model.
* **Validity:** in `dev_20261013_224947.jsonl`, the R2 and A rows are **invalid**; the L rows are valid. The main benchmark ran entirely on the corrected code. Both pilot files are kept unmodified.

## 8. Limitations

1. One synthetic corpus written by Claude subagents from a fact base; models may behave differently on human written documentation.
2. 50 test questions and a **single** main execution per configuration: results are descriptive; small differences (for example 96% vs 98%) are within what one more run could change.
3. About 47K tokens is well within both models' context windows. **This is not a long context stress test.** Long context cost and accuracy at 150K or 500K tokens were not measured.
4. Only the medium thinking level was benchmarked.
5. Retrieval settings (chunk size about 800 tokens, top 8, `gemini-embedding-2`) were fixed in advance and not tuned; other settings could change RAG results.
6. R2 captions come from Gemini 3.8 Flash, so R2 inherits Flash's diagram reading for both models.
7. Caching results reflect two days of requests and are not a statement about Google's caching in general.
8. The answer key is deterministic regex matching; any answer phrased in a way the patterns miss would count as incorrect. Unmatched cases should be reviewed by hand in the error report.

## 9. Reproducibility

Requirements: Python 3.11+, a Gemini API key on a billed project (Argon has no free tier).

```powershell
git clone <this repository>; cd argon-knowledge-lab
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:GEMINI_API_KEY = "..."
.\.venv\Scripts\python.exe corpus\check_corpus.py small          # free: verifies the frozen corpus
.\.venv\Scripts\python.exe run.py --split test --arms R1 R2 L A --models gemini-4-argon gemini-3.8-flash --levels medium --budget 15 --dry-run
.\.venv\Scripts\python.exe run.py --split test --arms R1 R2 L A --models gemini-4-argon gemini-3.8-flash --levels medium --budget 15
.\.venv\Scripts\python.exe score.py results\runs\<new file>.jsonl              # free
.\.venv\Scripts\python.exe analyze_results.py results\runs\<new file>.jsonl    # free
```

`run.py` always prints an estimate and asks for confirmation; `--budget` is a hard stop. Captions are already frozen, so `make_captions.py` is not needed for a rerun. Prices are in `src/argon_lab/pricing.py` (introductory Argon pricing ends 2026-11-30; rates double after). Model behavior and caching may differ on rerun.

## 10. Cost: local log vs billing

| Item | Logged cost |
|---|---|
| Probes (access, function calling, File Search, three caching probes) | about $0.48 |
| Diagram captions (4 Flash calls) | not logged; small |
| Pilot (including invalid arms) and rerun | $1.80 |
| Main benchmark | $8.31 |
| Embeddings (about 110K tokens) | not priced; Google's price for `gemini-embedding-2` was not available to us |
| **Total logged** | **about $10.60** |

The project owner reported seeing about $25 in billing. **This discrepancy is unresolved.** Possible causes not yet checked: a prepaid credit top-up shown as the charge, other usage on the same billing account, or token types our cost formula undercounts (image tokens, tool use tokens, or thinking tokens if `total_output_tokens` already includes them). Until reconciled against the AI Studio usage page per model, the costs in this README should be read as **estimates from API usage fields**, valid for comparing approaches but not as invoice totals.

## 11. Repository map

| Path | Content |
|---|---|
| `corpus/spec/` | Fact base, frozen questions and answer key, diagram sources (never sent to models) |
| `corpus/small/` | Documents, diagrams, frozen captions, SHA256 manifest |
| `src/argon_lab/` | Corpus loader, retrieval, the four arms, scoring, pricing |
| `run.py`, `score.py`, `analyze_results.py` | Runner with budget cap; deterministic scorer; offline analysis |
| `probes/` | API verification and caching probes |
| `results/runs/`, `results/scores/` | Raw JSONL and scored CSV files, unmodified |
| `docs/plan.md`, `docs/medium_outline.md` | Preregistered plan; article outline |
